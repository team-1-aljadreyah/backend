from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any
from collections import Counter
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import (
    NotFoundException,
    ConflictException,
    UnprocessableEntityException,
    ForbiddenException,
)
from app.database.models.profile import Profile, Doctor
from app.database.models.patient import Patient
from app.database.models.appointment import Appointment
from app.database.models.finance import InvoiceItem, Payment, CashClosing, Expense
from app.database.models.pharmacy import PharmacySale
from app.schemas.finance import (
    PayRequest,
    Invoice,
    InvoiceItemSchema,
    Payment as PaymentSchema,
    MoneySummary,
    ShiftSummary,
    CashClosingSchema,
    CloseShiftRequest,
    ExpenseSchema,
    ExpenseInput,
    ExpenseVoid,
    LedgerEntry,
    DoctorDues,
    CountRow,
    Report,
)
from app.services.audit_service import log_audit
from app.services.patient_service import compute_money_for_appointment
from app.core.idempotency import check_idempotency, save_idempotency_record

get_money_summary = compute_money_for_appointment


async def take_payment(
    db: AsyncSession,
    appt_id: int,
    req: PayRequest,
    method: str,
    user: Profile,
    ref_key: Optional[str] = None,
):
    stmt = select(Appointment, Patient).join(Patient, Appointment.patient_id == Patient.id).where(
        Appointment.id == appt_id
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise NotFoundException(message="Appointment not found", code="not_found")
    appt, patient = row

    if user.role == "patient" and patient.account_id != user.id:
        raise ForbiddenException(message="Access denied", code="forbidden")

    # Idempotency check with payload hashing
    target_key = ref_key or req.idempotency_key
    if target_key:
        cached = await check_idempotency(db, target_key, f"payment.{method}", req, user.id)
        if cached:
            return

    if appt.status == "no_show":
        raise ConflictException(message="Cannot take payment for no-show appointment", code="no_show")

    if req.amount <= 0:
        raise UnprocessableEntityException(message="Payment amount must be greater than 0", code="bad_amount")

    money = await compute_money_for_appointment(db, appt_id)
    rem_balance = money.balance.get(req.currency, 0.0)
    if req.amount > rem_balance + 0.01:  # Allow 1 cent tolerance for float rounding
        raise ConflictException(message=f"Amount exceeds outstanding balance ({rem_balance} {req.currency})", code="overpay")

    payment = Payment(
        appointment_id=appt_id,
        amount=req.amount,
        currency=req.currency,
        method=method,
        kind="payment",
        at=datetime.now(timezone.utc),
        by=user.name,
        reason="",
        ref_id=None,
        key=target_key,
    )
    db.add(payment)

    action = "payment.cash" if method == "cash" else "payment.online"
    await log_audit(db, user, action, patient.name)
    if target_key:
        await save_idempotency_record(db, target_key, f"payment.{method}", req, 200, {"success": True}, user.id)
    await db.commit()


async def get_today_invoices(db: AsyncSession) -> List[Invoice]:
    today = date.today()
    stmt = (
        select(Appointment, Patient.name, Doctor.name_ar)
        .join(Patient, Appointment.patient_id == Patient.id)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .where(Appointment.date == today, Appointment.status != "cancelled")
        .order_by(Appointment.time.asc())
    )
    rows = (await db.execute(stmt)).all()

    invoices = []
    for appt, patient_name, doctor_name in rows:
        # Items
        i_stmt = select(InvoiceItem).where(InvoiceItem.appointment_id == appt.id)
        items = (await db.execute(i_stmt)).scalars().all()
        # Payments
        p_stmt = select(Payment).where(Payment.appointment_id == appt.id)
        payments = (await db.execute(p_stmt)).scalars().all()
        # Money
        money = await compute_money_for_appointment(db, appt.id)

        invoices.append(
            Invoice(
                appointment_id=appt.id,
                patient_name=patient_name,
                doctor_name=doctor_name,
                date=str(appt.date),
                time=appt.time,
                status=appt.status,
                items=[
                    InvoiceItemSchema(
                        id=it.id,
                        label=it.label,
                        label_ar=it.label_ar,
                        kind=it.kind,
                        price=float(it.price),
                        currency=it.currency,
                    )
                    for it in items
                ],
                payments=[
                    PaymentSchema(
                        id=p.id,
                        amount=float(p.amount),
                        currency=p.currency,
                        method=p.method,
                        kind=p.kind,
                        at=p.at.isoformat(),
                        by=p.by,
                        reason=p.reason or "",
                    )
                    for p in payments
                ],
                money=money,
            )
        )
    return invoices


async def get_shift_summary(db: AsyncSession, user: Profile) -> ShiftSummary:
    # Find user's last closing
    c_stmt = select(CashClosing).where(CashClosing.by == user.name).order_by(CashClosing.id.desc()).limit(1)
    last_closing = (await db.execute(c_stmt)).scalar_one_or_none()

    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
    opened_at = last_closing.closed_at if (last_closing and last_closing.closed_at > today_start) else today_start

    # Get payments taken by user in this shift
    p_stmt = select(Payment).where(
        Payment.by == user.name,
        Payment.method == "cash",
        Payment.kind == "payment",
        Payment.at > opened_at,
    )
    payments = (await db.execute(p_stmt)).scalars().all()

    # Get reversals that undo any of these payments
    p_ids = [p.id for p in payments]
    reversed_ids = set()
    if p_ids:
        r_stmt = select(Payment.ref_id).where(Payment.ref_id.in_(p_ids), Payment.kind == "reversal")
        reversed_ids = set((await db.execute(r_stmt)).scalars().all())

    expected = {"IQD": 0.0, "USD": 0.0}
    valid_count = 0
    for p in payments:
        if p.id not in reversed_ids:
            expected[p.currency] += float(p.amount)
            valid_count += 1

    return ShiftSummary(
        opened_at=opened_at.isoformat(),
        payments=len(payments),
        expected=expected,
    )


async def close_shift(db: AsyncSession, req: CloseShiftRequest, user: Profile) -> CashClosingSchema:
    shift = await get_shift_summary(db, user)

    diff_iqd = req.counted.get("IQD", 0.0) - shift.expected.get("IQD", 0.0)
    diff_usd = req.counted.get("USD", 0.0) - shift.expected.get("USD", 0.0)

    closing = CashClosing(
        by=user.name,
        opened_at=datetime.fromisoformat(shift.opened_at),
        closed_at=datetime.now(timezone.utc),
        payments=shift.payments,
        expected_iqd=shift.expected.get("IQD", 0.0),
        expected_usd=shift.expected.get("USD", 0.0),
        counted_iqd=req.counted.get("IQD", 0.0),
        counted_usd=req.counted.get("USD", 0.0),
        difference_iqd=diff_iqd,
        difference_usd=diff_usd,
        note=req.note.strip(),
    )
    db.add(closing)
    await db.flush()

    await log_audit(db, user, "cash.close", f"{int(diff_iqd):,} IQD")
    await db.commit()

    return CashClosingSchema(
        id=closing.id,
        by=closing.by,
        opened_at=closing.opened_at.isoformat(),
        closed_at=closing.closed_at.isoformat(),
        payments=closing.payments,
        expected={"IQD": float(closing.expected_iqd), "USD": float(closing.expected_usd)},
        counted={"IQD": float(closing.counted_iqd), "USD": float(closing.counted_usd)},
        difference={"IQD": float(closing.difference_iqd), "USD": float(closing.difference_usd)},
        note=closing.note,
    )


async def list_cash_closings(db: AsyncSession, user: Profile) -> List[CashClosingSchema]:
    stmt = select(CashClosing).order_by(CashClosing.id.desc())
    if user.role == "reception":
        stmt = stmt.where(CashClosing.by == user.name)

    closings = (await db.execute(stmt)).scalars().all()
    return [
        CashClosingSchema(
            id=c.id,
            by=c.by,
            opened_at=c.opened_at.isoformat(),
            closed_at=c.closed_at.isoformat(),
            payments=c.payments,
            expected={"IQD": float(c.expected_iqd), "USD": float(c.expected_usd)},
            counted={"IQD": float(c.counted_iqd), "USD": float(c.counted_usd)},
            difference={"IQD": float(c.difference_iqd), "USD": float(c.difference_usd)},
            note=c.note,
        )
        for c in closings
    ]


async def list_expenses(db: AsyncSession, month_str: str) -> List[ExpenseSchema]:
    # Match YYYY-MM prefix
    stmt = select(Expense).order_by(Expense.date.desc(), Expense.id.desc())
    expenses = (await db.execute(stmt)).scalars().all()

    filtered = [e for e in expenses if str(e.date).startswith(month_str)]
    return [
        ExpenseSchema(
            id=e.id,
            date=str(e.date),
            category=e.category,
            amount=float(e.amount),
            currency=e.currency,
            note=e.note,
            by=e.by,
            at=e.at.isoformat(),
            voided=ExpenseVoid(by=e.voided_by, at=e.voided_at.isoformat(), reason=e.voided_reason) if e.voided_by else None,
        )
        for e in filtered
    ]


async def add_expense(db: AsyncSession, req: ExpenseInput, user: Profile) -> ExpenseSchema:
    exp_date = date.fromisoformat(req.date)
    if exp_date > date.today():
        raise UnprocessableEntityException(message="Expense date cannot be in the future", code="future_date")
    if req.amount <= 0:
        raise UnprocessableEntityException(message="Amount must be positive", code="bad_amount")

    expense = Expense(
        date=exp_date,
        category=req.category,
        amount=req.amount,
        currency=req.currency,
        note=req.note.strip(),
        by=user.name,
        at=datetime.now(timezone.utc),
    )
    db.add(expense)
    await db.flush()

    await log_audit(db, user, "expense.add", f"{req.note.strip() or req.category} · {int(req.amount):,} {req.currency}")
    await db.commit()

    return ExpenseSchema(
        id=expense.id,
        date=str(expense.date),
        category=expense.category,
        amount=float(expense.amount),
        currency=expense.currency,
        note=expense.note,
        by=expense.by,
        at=expense.at.isoformat(),
        voided=None,
    )


async def void_expense(db: AsyncSession, expense_id: int, reason: str, user: Profile) -> ExpenseSchema:
    stmt = select(Expense).where(Expense.id == expense_id)
    exp = (await db.execute(stmt)).scalar_one_or_none()
    if not exp:
        raise NotFoundException(message="Expense not found", code="not_found")
    if exp.voided_by:
        raise ConflictException(message="Expense is already voided", code="already_voided")
    if len(reason.strip()) < 3:
        raise UnprocessableEntityException(message="Void reason required (at least 3 characters)", code="reason_needed")

    exp.voided_by = user.name
    exp.voided_at = datetime.now(timezone.utc)
    exp.voided_reason = reason.strip()

    await log_audit(db, user, "expense.void", f"{exp.note or exp.category} · {reason.strip()}")
    await db.commit()

    return ExpenseSchema(
        id=exp.id,
        date=str(exp.date),
        category=exp.category,
        amount=float(exp.amount),
        currency=exp.currency,
        note=exp.note,
        by=exp.by,
        at=exp.at.isoformat(),
        voided=ExpenseVoid(by=exp.voided_by, at=exp.voided_at.isoformat(), reason=exp.voided_reason),
    )


async def list_ledger(db: AsyncSession) -> List[LedgerEntry]:
    # Query all payments newest first
    stmt = (
        select(Payment, Appointment, Patient.name, Doctor.name_ar)
        .join(Appointment, Payment.appointment_id == Appointment.id)
        .join(Patient, Appointment.patient_id == Patient.id)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .order_by(Payment.id.desc())
    )
    rows = (await db.execute(stmt)).all()

    # Query all ref_ids of existing reversals
    rev_stmt = select(Payment.ref_id).where(Payment.ref_id.is_not(None))
    reversed_ref_ids = set((await db.execute(rev_stmt)).scalars().all())

    ledger = []
    for p, appt, p_name, doc_name in rows:
        is_rev = p.kind == "payment" and (p.id not in reversed_ref_ids)
        ledger.append(
            LedgerEntry(
                id=p.id,
                appointment_id=p.appointment_id,
                amount=float(p.amount),
                currency=p.currency,
                method=p.method,
                kind=p.kind,
                at=p.at.isoformat(),
                by=p.by,
                reason=p.reason or "",
                patient_name=p_name,
                doctor_name=doc_name,
                reversible=is_rev,
            )
        )
    return ledger


async def reverse_payment(db: AsyncSession, payment_id: int, reason: str, user: Profile):
    stmt = select(Payment).where(Payment.id == payment_id)
    p = (await db.execute(stmt)).scalar_one_or_none()
    if not p:
        raise NotFoundException(message="Payment not found", code="not_found")
    if p.kind != "payment":
        raise ConflictException(message="Only regular payments can be reversed", code="already_reversed")

    chk = select(Payment).where(Payment.ref_id == payment_id)
    if (await db.execute(chk)).scalar_one_or_none():
        raise ConflictException(message="Payment has already been reversed", code="already_reversed")

    rev = Payment(
        appointment_id=p.appointment_id,
        amount=p.amount,
        currency=p.currency,
        method=p.method,
        kind="reversal",
        at=datetime.now(timezone.utc),
        by=user.name,
        reason=reason.strip(),
        ref_id=payment_id,
        key=f"reverse:{payment_id}",
    )
    db.add(rev)

    # Get patient name for audit
    appt_stmt = select(Patient.name).join(Appointment, Appointment.patient_id == Patient.id).where(
        Appointment.id == p.appointment_id
    )
    p_name = (await db.execute(appt_stmt)).scalar_one() or ""

    await log_audit(db, user, "payment.reverse", f"{p_name} · {reason.strip()}")
    await db.commit()


async def get_doctor_dues(db: AsyncSession, month_str: str) -> List[DoctorDues]:
    stmt = select(Doctor).order_by(Doctor.id)
    doctors = (await db.execute(stmt)).scalars().all()

    dues = []
    for doc in doctors:
        # Appointments in month visited
        a_stmt = select(Appointment).where(
            Appointment.doctor_id == doc.id,
            Appointment.status.in_(["arrived", "in_progress", "done"]),
        )
        all_appts = (await db.execute(a_stmt)).scalars().all()
        month_appts = [a for a in all_appts if str(a.date).startswith(month_str)]

        visit_income = 0.0
        procedure_income = 0.0
        visits_count = len(month_appts)

        for a in month_appts:
            money = await compute_money_for_appointment(db, a.id)
            tot_iqd = money.total.get("IQD", 0.0)
            paid_iqd = money.paid.get("IQD", 0.0)
            share = max(0.0, min(1.0, paid_iqd / tot_iqd)) if tot_iqd > 0 else 0.0

            i_stmt = select(InvoiceItem).where(InvoiceItem.appointment_id == a.id, InvoiceItem.currency == "IQD")
            items = (await db.execute(i_stmt)).scalars().all()
            for it in items:
                if it.kind == "visit":
                    visit_income += float(it.price) * share
                elif it.kind == "procedure":
                    procedure_income += float(it.price) * share

        doc_share = (visit_income * (100.0 - float(doc.clinic_percent)) + procedure_income * (100.0 - float(doc.service_percent))) / 100.0
        clinic_share = (visit_income + procedure_income) - doc_share

        dues.append(
            DoctorDues(
                doctor_id=doc.id,
                doctor_name=doc.name_ar,
                visits=visits_count,
                visit_income=round(visit_income),
                procedure_income=round(procedure_income),
                doctor_share=round(doc_share),
                clinic_share=round(clinic_share),
            )
        )
    return dues


async def get_report_summary(db: AsyncSession, month_str: str) -> Report:
    # Query appointments in month visited
    a_stmt = (
        select(Appointment, Doctor.name_ar, Patient.name)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .join(Patient, Appointment.patient_id == Patient.id)
    )
    all_rows = (await db.execute(a_stmt)).all()

    month_visited = [r for r in all_rows if str(r[0].date).startswith(month_str) and r[0].status in ("arrived", "in_progress", "done")]
    today_visited = [r for r in all_rows if r[0].date == date.today() and r[0].status in ("arrived", "in_progress", "done")]
    month_no_shows = [r for r in all_rows if str(r[0].date).startswith(month_str) and r[0].status == "no_show"]

    # Payments
    p_stmt = select(Payment)
    all_payments = (await db.execute(p_stmt)).scalars().all()
    month_payments = [p for p in all_payments if str(p.at.date()).startswith(month_str)]
    today_payments = [p for p in all_payments if p.at.date() == date.today()]

    collected = {"IQD": 0.0, "USD": 0.0}
    for p in month_payments:
        amt = float(p.amount) if p.kind == "payment" else -float(p.amount)
        collected[p.currency] += amt

    today_collected = {"IQD": 0.0, "USD": 0.0}
    for p in today_payments:
        amt = float(p.amount) if p.kind == "payment" else -float(p.amount)
        today_collected[p.currency] += amt

    # Billed
    billed = {"IQD": 0.0, "USD": 0.0}
    today_billed = {"IQD": 0.0, "USD": 0.0}
    m_appt_ids = {r[0].id for r in month_visited}
    t_appt_ids = {r[0].id for r in today_visited}

    if m_appt_ids:
        i_stmt = select(InvoiceItem).where(InvoiceItem.appointment_id.in_(list(m_appt_ids)))
        for it in (await db.execute(i_stmt)).scalars().all():
            billed[it.currency] += float(it.price)

    if t_appt_ids:
        it_stmt = select(InvoiceItem).where(InvoiceItem.appointment_id.in_(list(t_appt_ids)))
        for it in (await db.execute(it_stmt)).scalars().all():
            today_billed[it.currency] += float(it.price)

    # Pharmacy sales
    s_stmt = select(PharmacySale)
    all_sales = (await db.execute(s_stmt)).scalars().all()
    pharmacy_month = sum(float(s.total) for s in all_sales if str(s.at.date()).startswith(month_str))
    pharmacy_today = sum(float(s.total) for s in all_sales if s.at.date() == date.today())

    # Expenses
    e_stmt = select(Expense).where(Expense.voided_by.is_(None))
    expenses_rows = (await db.execute(e_stmt)).scalars().all()
    expenses = {"IQD": 0.0, "USD": 0.0}
    for e in expenses_rows:
        if str(e.date).startswith(month_str):
            expenses[e.currency] += float(e.amount)

    profit = {
        "IQD": collected["IQD"] + pharmacy_month - expenses["IQD"],
        "USD": collected["USD"] - expenses["USD"],
    }

    # Breakdown counts
    day_counts = Counter(str(r[0].date) for r in month_visited)
    by_day = [CountRow(label=d, count=c) for d, c in sorted(day_counts.items())]

    doc_counts = Counter(r[1] for r in month_visited)
    by_doctor = [CountRow(label=d, count=c) for d, c in doc_counts.most_common()]

    branch_counts = Counter(r[0].branch for r in month_visited)
    by_branch = [CountRow(label=b, count=c) for b, c in branch_counts.most_common()]

    no_show_counts = Counter(r[2] for r in month_no_shows)
    top_no_shows = [CountRow(label=name, count=c) for name, c in no_show_counts.most_common(5)]

    return Report(
        month=month_str,
        by_day=by_day,
        by_doctor=by_doctor,
        by_branch=by_branch,
        top_no_shows=top_no_shows,
        billed=billed,
        collected=collected,
        today_billed=today_billed,
        today_collected=today_collected,
        pharmacy_month=pharmacy_month,
        pharmacy_today=pharmacy_today,
        expenses=expenses,
        profit=profit,
    )
