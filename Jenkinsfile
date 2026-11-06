
pipeline {

    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 45, unit: 'MINUTES')
    }

    parameters {
        booleanParam(
            name: 'IMAGE_RETENTION_DRY_RUN',
            defaultValue: true,
            description: 'Safe mode: preview image cleanup without deleting images. Disable only after reviewing the dry-run logs.'
        )
    }

    triggers {
        pollSCM('H/2 * * * *')
    }

    environment {

        IMAGE_REPOSITORY = 'aljadreyah-backend'

        CONTAINER_NAME = 'aljadreyah-backend'

        DEPLOY_DIR = '/opt/aljadreyah/deploy'

        COMPOSE_FILE = '/opt/aljadreyah/deploy/compose.production.yaml'

        COMPOSE_PROJECT = 'aljadreyah'
    }


    stages {

        // =========================================
        // 1. CHECKOUT
        // =========================================

        stage('Checkout') {

            steps {

                deleteDir()

                checkout scm

                script {

                    env.GIT_SHA = sh(
                        script: 'git rev-parse --short=12 HEAD',
                        returnStdout: true
                    ).trim()

                    env.IMAGE_TAG =
                        "${env.BUILD_NUMBER}-${env.GIT_SHA}"

                    env.NEW_IMAGE =
                        "${env.IMAGE_REPOSITORY}:${env.IMAGE_TAG}"

                }
            }
        }


        // =========================================
        // 2. VERIFY ENVIRONMENT
        // =========================================

        stage('Verify Environment') {

            steps {

                sh '''#!/usr/bin/env bash

                    set -Eeuo pipefail

                    docker version

                    docker compose version

                    docker info >/dev/null

                    test -r /etc/aljadreyah/backend.env

                    test -d /opt/aljadreyah/backend/shared/uploads

                    test -w /opt/aljadreyah/deploy

                    echo "Production environment verified."

                '''
            }
        }


        // =========================================
        // 3. AUTOMATED TESTING
        // =========================================

        stage('Run Tests') {

            steps {

                sh '''#!/usr/bin/env bash

                    set -Eeuo pipefail

                    mkdir -p reports

                    docker run --rm \\
                        --user "$(id -u):$(id -g)" \\
                        -e APP_ENV=testing \\
                        -e APP_DEBUG=false \\
                        -e APP_TIMEZONE=Asia/Baghdad \\
                        -e SECRET_KEY=ci-only-secret-key-32-characters-minimum-123 \\
                        -e DATABASE_URL=sqlite+aiosqlite:///./test_ci.db \\
                        -e SUPABASE_URL=https://mock-supabase.local \\
                        -e SUPABASE_ANON_KEY=ci-placeholder \\
                        -e SUPABASE_SERVICE_ROLE_KEY=ci-placeholder \\
                        -e SUPABASE_STORAGE_BUCKET=lab-results \\
                        -e FRONTEND_ORIGINS=http://localhost:3000 \\
                        -v "$WORKSPACE:/workspace" \\
                        -w /workspace \\
                        python:3.12-slim \\
                        sh -ec '

                            python -m venv /tmp/ci-venv

                            /tmp/ci-venv/bin/pip install \\
                                --no-cache-dir \\
                                -r requirements-dev.txt

                            /tmp/ci-venv/bin/python \\
                                -m compileall -q app database

                            /tmp/ci-venv/bin/python \\
                                -m ruff check .

                            /tmp/ci-venv/bin/python \\
                                -m pytest \\
                                -v \\
                                --asyncio-mode=auto \\
                                --junitxml=reports/junit.xml

                        '

                '''
            }

            post {

                always {

                    junit(
                        testResults: 'reports/junit.xml',
                        allowEmptyResults: true
                    )

                }
            }
        }


        // =========================================
        // 4. BUILD PRODUCTION IMAGE
        // =========================================

        stage('Build Docker Image') {

            steps {

                sh '''#!/usr/bin/env bash

                    set -Eeuo pipefail

                    echo "======================================"

                    echo "BUILDING PRODUCTION IMAGE"

                    echo "IMAGE: $NEW_IMAGE"

                    echo "======================================"

                    docker build \\
                        --pull \\
                        --label "org.opencontainers.image.revision=$GIT_SHA" \\
                        --label "com.aljadreyah.pipeline.managed=true" \\
                        --label "com.aljadreyah.pipeline.build-number=$BUILD_NUMBER" \\
                        --label "com.aljadreyah.pipeline.git-sha=$GIT_SHA" \\
                        --tag "$NEW_IMAGE" \\
                        .

                    docker image inspect "$NEW_IMAGE" >/dev/null

                    echo "Docker image built successfully."

                '''
            }
        }


        // =========================================
        // 5. DEPLOY PRODUCTION
        // =========================================

        stage('Deploy Production') {

            steps {

                sh '''#!/usr/bin/env bash

set -Eeuo pipefail


echo "======================================"
echo "STARTING PRODUCTION DEPLOYMENT"
echo "======================================"


# =========================================
# 1. INSTALL PRODUCTION COMPOSE FILE
# =========================================

install -m 0644 \\
    "$WORKSPACE/compose.production.yaml" \\
    "$COMPOSE_FILE"

cd "$DEPLOY_DIR"


# =========================================
# 2. DETECT PREVIOUS IMAGE
# =========================================

PREVIOUS_IMAGE="$(
    docker inspect \\
        --format '{{.Config.Image}}' \\
        "$CONTAINER_NAME" 2>/dev/null || true
)"

PREVIOUS_IMAGE_ID="$(
    docker inspect \\
        --format '{{.Image}}' \\
        "$CONTAINER_NAME" 2>/dev/null || true
)"


# If no running container exists, use saved deployment reference.

if [[ -z "$PREVIOUS_IMAGE" && -f "$DEPLOY_DIR/.env" ]]; then

    PREVIOUS_IMAGE="$(
        sed -n 's/^BACKEND_IMAGE=//p' "$DEPLOY_DIR/.env" |
        tail -n 1
    )"

fi


# Resolve previous image ID.

if [[ -n "$PREVIOUS_IMAGE" && -z "$PREVIOUS_IMAGE_ID" ]]; then

    PREVIOUS_IMAGE_ID="$(
        docker image inspect \\
            --format '{{.Id}}' \\
            "$PREVIOUS_IMAGE" 2>/dev/null || true
    )"

fi


# Restore the previous image reference if its tag was removed.

if [[ -n "$PREVIOUS_IMAGE" && -n "$PREVIOUS_IMAGE_ID" ]]; then

    if ! docker image inspect "$PREVIOUS_IMAGE" >/dev/null 2>&1; then

        docker tag "$PREVIOUS_IMAGE_ID" "$PREVIOUS_IMAGE"

    fi

fi


ROLLBACK_IMAGE="$PREVIOUS_IMAGE"


# If only the image ID is available, create a rollback reference.

if [[ -z "$ROLLBACK_IMAGE" && -n "$PREVIOUS_IMAGE_ID" ]]; then

    ROLLBACK_IMAGE="${IMAGE_REPOSITORY}:rollback-${BUILD_NUMBER}-${GIT_SHA}"

    docker tag "$PREVIOUS_IMAGE_ID" "$ROLLBACK_IMAGE"

fi


echo "Previous image: ${PREVIOUS_IMAGE:-NONE}"

echo "Previous image ID: ${PREVIOUS_IMAGE_ID:-NONE}"

echo "New image: $NEW_IMAGE"

echo "Rollback reference: ${ROLLBACK_IMAGE:-NONE}"


# =========================================
# 3. VALIDATE COMPOSE CONFIGURATION
# =========================================

BACKEND_IMAGE="$NEW_IMAGE" docker compose \\
    -p "$COMPOSE_PROJECT" \\
    -f "$COMPOSE_FILE" \\
    config --quiet


# =========================================
# 4. ATOMIC DEPLOYMENT ENVIRONMENT WRITER
# =========================================

write_deploy_env() {

    local image_ref="$1"

    local temporary_file="$DEPLOY_DIR/.env.next"

    printf 'BACKEND_IMAGE=%s\\n' "$image_ref" > "$temporary_file" || return 1

    chmod 600 "$temporary_file" || return 1

    mv -f "$temporary_file" "$DEPLOY_DIR/.env" || return 1

}


# =========================================
# 5. ROLLBACK FUNCTION
# =========================================

rollback() {

    echo "======================================"

    echo "STARTING AUTOMATIC ROLLBACK"

    echo "======================================"


    if [[ -n "$ROLLBACK_IMAGE" ]]; then

        if ! docker image inspect "$ROLLBACK_IMAGE" >/dev/null 2>&1; then

            echo "ERROR: Previous image is unavailable."

            return 1

        fi


        echo "Restoring: $ROLLBACK_IMAGE"


        if ! BACKEND_IMAGE="$ROLLBACK_IMAGE" docker compose \\
            -p "$COMPOSE_PROJECT" \\
            -f "$COMPOSE_FILE" \\
            up -d --no-deps --force-recreate backend; then

            echo "ERROR: Rollback container could not start."

            return 1

        fi


        echo "Checking restored application health..."

        local rollback_healthy=0

        local rollback_status

        local rollback_state


        for attempt in $(seq 1 45); do

            rollback_status="$(
                docker inspect \\
                    --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' \\
                    "$CONTAINER_NAME" 2>/dev/null || echo missing
            )"

            rollback_state="$(
                docker inspect \\
                    --format '{{.State.Status}}' \\
                    "$CONTAINER_NAME" 2>/dev/null || echo missing
            )"


            echo "Rollback health $attempt/45: $rollback_status | $rollback_state"


            if [[ "$rollback_status" == "healthy" ]]; then

                rollback_healthy=1

                break

            fi


            if [[ "$rollback_status" == "unhealthy" ]] || \\
               [[ "$rollback_state" == "exited" ]] || \\
               [[ "$rollback_state" == "dead" ]] || \\
               [[ "$rollback_state" == "missing" ]]; then

                break

            fi

            sleep 2

        done


        if [[ "$rollback_healthy" -ne 1 ]]; then

            echo "ERROR: Restored application did not become healthy."

            docker logs --tail 200 "$CONTAINER_NAME" || true

            return 1

        fi


        # Save fallback rollback reference if necessary.

        if [[ "$ROLLBACK_IMAGE" != "$PREVIOUS_IMAGE" ]]; then

            write_deploy_env "$ROLLBACK_IMAGE" || {
                echo "WARNING: Could not update rollback deployment reference."
                return 1
            }

        fi


        echo "ROLLBACK SUCCESSFUL"

        echo "RESTORED IMAGE: $ROLLBACK_IMAGE"

        echo "RESTORED HEALTH: HEALTHY"

        return 0

    else

        echo "No previous image is available."

        echo "Removing failed deployment container."

        docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

        return 0

    fi

}


# =========================================
# 6. DEPLOY NEW CONTAINER
# =========================================

echo "Starting new production container..."


if ! BACKEND_IMAGE="$NEW_IMAGE" docker compose \\
    -p "$COMPOSE_PROJECT" \\
    -f "$COMPOSE_FILE" \\
    up -d --no-deps --force-recreate backend; then

    echo "ERROR: Docker Compose deployment failed."

    docker logs --tail 200 "$CONTAINER_NAME" || true

    rollback || echo "CRITICAL: Rollback requires manual attention."

    exit 1

fi


# =========================================
# 7. HEALTH CHECK
# =========================================

echo "Waiting for application readiness..."

HEALTHY=0


for attempt in $(seq 1 90); do

    STATUS="$(
        docker inspect \\
            --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' \\
            "$CONTAINER_NAME" 2>/dev/null || echo missing
    )"

    STATE="$(
        docker inspect \\
            --format '{{.State.Status}}' \\
            "$CONTAINER_NAME" 2>/dev/null || echo missing
    )"


    echo "Health attempt $attempt/90: $STATUS | Container: $STATE"


    if [[ "$STATUS" == "healthy" ]]; then

        HEALTHY=1

        echo "Application is healthy."

        break

    fi


    if [[ "$STATUS" == "unhealthy" ]] || \\
       [[ "$STATUS" == "missing" ]] || \\
       [[ "$STATUS" == "no-healthcheck" ]] || \\
       [[ "$STATE" == "exited" ]] || \\
       [[ "$STATE" == "dead" ]]; then

        echo "Application health verification failed."

        break

    fi


    sleep 2

done


# =========================================
# 8. FAILED HEALTH CHECK
# =========================================

if [[ "$HEALTHY" -ne 1 ]]; then

    echo "======================================"

    echo "DEPLOYMENT HEALTH CHECK FAILED"

    echo "======================================"


    echo "Container state:"

    docker inspect \\
        --format '{{json .State}}' \\
        "$CONTAINER_NAME" || true


    echo "Health check details:"

    docker inspect \\
        --format '{{json .State.Health}}' \\
        "$CONTAINER_NAME" || true


    echo "Last 200 container log lines:"

    docker logs --tail 200 "$CONTAINER_NAME" || true


    # Rollback before marking the image failed.

    rollback || echo "CRITICAL: Automatic rollback failed."

    exit 1

fi


# =========================================
# 9. MARK HEALTH CHECK SUCCESS
# =========================================

echo "Health verification passed."

: > "$WORKSPACE/.deployment-health-passed"


# =========================================
# 10. CREATE SUCCESS IMAGE TAG
# =========================================

SUCCESS_IMAGE="${IMAGE_REPOSITORY}:success-${IMAGE_TAG}"


if ! docker tag "$NEW_IMAGE" "$SUCCESS_IMAGE"; then

    echo "ERROR: Could not tag successful image."

    rm -f "$WORKSPACE/.deployment-health-passed"

    rollback || echo "CRITICAL: Rollback failed."

    exit 1

fi


echo "Successful image: $SUCCESS_IMAGE"


# =========================================
# 11. SAVE ACTIVE IMAGE
# =========================================

if ! write_deploy_env "$NEW_IMAGE"; then

    echo "ERROR: Could not save active image reference."

    docker image rm "$SUCCESS_IMAGE" >/dev/null 2>&1 || true

    rm -f "$WORKSPACE/.deployment-health-passed"

    rollback || echo "CRITICAL: Rollback failed."

    exit 1

fi


# Commit marker protects healthy deployment
# from being classified as failed in post.

: > "$WORKSPACE/.deployment-committed"


# =========================================
# 12. IMAGE RETENTION FUNCTIONS
# =========================================

# Protect images used by ANY existing container.

image_is_used_by_any_container() {

    local target_id="$1"

    local container_id

    local container_image_id


    while IFS= read -r container_id; do

        [[ -n "$container_id" ]] || continue


        container_image_id="$(
            docker inspect \\
                --format '{{.Image}}' \\
                "$container_id" 2>/dev/null || true
        )"


        if [[ "$container_image_id" == "$target_id" ]]; then

            return 0

        fi

    done < <(docker ps -aq)


    return 1

}


# Keep the newest N images for a given status.
# Active, previous and container-used images are always protected.

prune_status_images() {

    local status_prefix="$1"

    local keep_count="$2"

    local active_id="$3"

    local previous_id="$4"

    local tag

    local image_ref

    local image_id

    local managed

    local base_tag

    local base_ref

    local base_id

    local kept=0

    local -a tags=()


    declare -A seen_ids=()


    echo "======================================"

    echo "IMAGE RETENTION: $status_prefix"

    echo "KEEP COUNT: $keep_count"

    echo "DRY RUN: $IMAGE_RETENTION_DRY_RUN"

    echo "======================================"


    # Sort managed status tags by descending Jenkins build number.

    mapfile -t tags < <(

        docker image ls \\
            --format '{{.Tag}}' \\
            "$IMAGE_REPOSITORY" |

        awk -F- -v prefix="$status_prefix" '

            $1 == prefix &&
            $2 ~ /^[0-9]+$/ &&
            $3 ~ /^[[:xdigit:]]+$/ {

                print $0

            }

        ' |

        LC_ALL=C sort -t- -k2,2nr -k3,3r

    )


    for tag in "${tags[@]}"; do

        image_ref="${IMAGE_REPOSITORY}:${tag}"


        image_id="$(
            docker image inspect \\
                --format '{{.Id}}' \\
                "$image_ref" 2>/dev/null || true
        )"


        [[ -n "$image_id" ]] || continue


        # Only remove images created by this pipeline.

        managed="$(
            docker image inspect \\
                --format '{{ index .Config.Labels "com.aljadreyah.pipeline.managed" }}' \\
                "$image_ref" 2>/dev/null || true
        )"


        if [[ "$managed" != "true" ]]; then

            echo "SKIP UNMANAGED IMAGE: $image_ref"

            continue

        fi


        # Protect active image.

        if [[ "$image_id" == "$active_id" ]]; then

            echo "PROTECTED ACTIVE IMAGE: $image_ref"

            continue

        fi


        # Protect previous rollback image.

        if [[ -n "$previous_id" && "$image_id" == "$previous_id" ]]; then

            echo "PROTECTED PREVIOUS IMAGE: $image_ref"

            continue

        fi


        # Protect every image used by any Docker container.

        if image_is_used_by_any_container "$image_id"; then

            echo "PROTECTED CONTAINER-REFERENCED IMAGE: $image_ref"

            continue

        fi


        # Count unique images, not duplicate tags.

        if [[ -n "${seen_ids[$image_id]:-}" ]]; then

            echo "DUPLICATE IMAGE ID: $image_ref"

            continue

        fi


        seen_ids["$image_id"]=1


        # Keep newest images.

        if (( kept < keep_count )); then

            kept=$((kept + 1))

            echo "KEEP: $image_ref"

            continue

        fi


        # Expired image.

        echo "EXPIRED IMAGE: $image_ref"


        base_tag="${tag#${status_prefix}-}"

        base_ref="${IMAGE_REPOSITORY}:${base_tag}"


        base_id="$(
            docker image inspect \\
                --format '{{.Id}}' \\
                "$base_ref" 2>/dev/null || true
        )"


        if [[ "$IMAGE_RETENTION_DRY_RUN" == "true" ]]; then

            echo "DRY RUN: WOULD REMOVE $image_ref"

            if [[ "$base_id" == "$image_id" ]]; then

                echo "DRY RUN: WOULD REMOVE $base_ref"

            fi

            continue

        fi


        # Remove only the expired status tag.

        if ! docker image rm "$image_ref"; then

            echo "WARNING: Could not remove $image_ref"

            continue

        fi


        # Remove matching original build tag only if it points
        # to exactly the same managed image ID.

        if [[ "$base_id" == "$image_id" ]]; then

            if ! docker image rm "$base_ref"; then

                echo "WARNING: Could not remove $base_ref"

            fi

        fi


        echo "REMOVED EXPIRED IMAGE: $image_ref"

    done


    echo "RETENTION FINISHED: $status_prefix"

}


# =========================================
# 13. RUN IMAGE RETENTION AFTER HEALTHY
# =========================================

ACTIVE_IMAGE_ID="$(
    docker inspect \\
        --format '{{.Image}}' \\
        "$CONTAINER_NAME"
)"


echo "Active image ID: $ACTIVE_IMAGE_ID"

echo "Previous image ID: ${PREVIOUS_IMAGE_ID:-NONE}"


case "${IMAGE_RETENTION_DRY_RUN:-true}" in

    true|TRUE|1)

        IMAGE_RETENTION_DRY_RUN=true

        ;;

    false|FALSE|0)

        IMAGE_RETENTION_DRY_RUN=false

        ;;

    *)

        echo "WARNING: Invalid retention mode."

        echo "Cleanup disabled for safety."

        IMAGE_RETENTION_DRY_RUN=true

        ;;

esac


# Last 5 successful images.

prune_status_images \\
    success \\
    5 \\
    "$ACTIVE_IMAGE_ID" \\
    "$PREVIOUS_IMAGE_ID" || echo "WARNING: Successful image cleanup encountered an error."


# Last 3 failed images.

prune_status_images \\
    failed \\
    3 \\
    "$ACTIVE_IMAGE_ID" \\
    "$PREVIOUS_IMAGE_ID" || echo "WARNING: Failed image cleanup encountered an error."


# =========================================
# 14. DEPLOYMENT SUCCESS
# =========================================

echo "======================================"

echo "PRODUCTION DEPLOYMENT SUCCESSFUL"

echo "======================================"

echo "IMAGE: $NEW_IMAGE"

echo "SUCCESS IMAGE: $SUCCESS_IMAGE"

echo "CONTAINER: $CONTAINER_NAME"

echo "PORT: 8000"

echo "HEALTH: HEALTHY"

echo "RETENTION DRY RUN: $IMAGE_RETENTION_DRY_RUN"

echo "======================================"

                '''
            }
        }

    }


    // =========================================
    // 6. PIPELINE POST ACTIONS
    // =========================================

    post {

        success {

            echo 'CI/CD pipeline completed successfully.'

            echo 'Production deployment is healthy.'

        }


        // Run on FAILURE, UNSTABLE or ABORTED.
        // Never run Docker cleanup here.

        unsuccessful {

            script {

                sh '''#!/usr/bin/env bash

set +e


echo "======================================"

echo "PIPELINE UNSUCCESSFUL"

echo "CHECKING FAILED IMAGE RETENTION"

echo "======================================"


if [[ -z "${NEW_IMAGE:-}" || -z "${IMAGE_TAG:-}" ]]; then

    echo "No production image was created."

    exit 0

fi


# If already committed, do not classify as failed.

if [[ -f "$WORKSPACE/.deployment-committed" ]]; then

    echo "Deployment was already committed successfully."

    echo "No failed tag will be created."

    exit 0

fi


# Recover a healthy deployment if Jenkins was interrupted
# after Health Check but before the deployment commit marker.

if [[ -f "$WORKSPACE/.deployment-health-passed" ]]; then

    echo "Health check previously passed. Verifying active container..."


    CURRENT_IMAGE_ID="$(
        docker inspect \\
            --format '{{.Image}}' \\
            "$CONTAINER_NAME" 2>/dev/null
    )"


    NEW_IMAGE_ID="$(
        docker image inspect \\
            --format '{{.Id}}' \\
            "$NEW_IMAGE" 2>/dev/null
    )"


    CURRENT_HEALTH="$(
        docker inspect \\
            --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' \\
            "$CONTAINER_NAME" 2>/dev/null
    )"


    if [[ -n "$CURRENT_IMAGE_ID" ]] && \\
       [[ "$CURRENT_IMAGE_ID" == "$NEW_IMAGE_ID" ]] && \\
       [[ "$CURRENT_HEALTH" == "healthy" ]]; then


        SUCCESS_IMAGE="${IMAGE_REPOSITORY}:success-${IMAGE_TAG}"


        if docker tag "$NEW_IMAGE" "$SUCCESS_IMAGE"; then

            if printf 'BACKEND_IMAGE=%s\\n' "$NEW_IMAGE" \\
                > "$DEPLOY_DIR/.env.recovery.next" && \\

               chmod 600 "$DEPLOY_DIR/.env.recovery.next" && \\

               mv -f "$DEPLOY_DIR/.env.recovery.next" "$DEPLOY_DIR/.env"; then


                touch "$WORKSPACE/.deployment-committed"

                echo "Healthy deployment successfully recovered."

                exit 0

            fi

        fi

    fi

fi


# Preserve failed image if the build completed.

if docker image inspect "$NEW_IMAGE" >/dev/null 2>&1; then

    FAILED_IMAGE="${IMAGE_REPOSITORY}:failed-${IMAGE_TAG}"

    if docker tag "$NEW_IMAGE" "$FAILED_IMAGE"; then

        echo "Failed image preserved: $FAILED_IMAGE"

    else

        echo "WARNING: Could not create failed image tag."

    fi

else

    echo "No completed Docker image is available."

fi


echo "No image cleanup will run on unsuccessful pipeline."

echo "======================================"

                '''

            }

            echo 'Failed deployment preserved. No Docker image cleanup executed.'

        }


        always {

            echo 'Pipeline execution finished.'

        }

    }

}
