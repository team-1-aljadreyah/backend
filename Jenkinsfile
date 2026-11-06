
pipeline {

    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 45, unit: 'MINUTES')
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

        // =====================================
        // 1. CHECKOUT
        // =====================================

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


        // =====================================
        // 2. VERIFY DOCKER & SERVER
        // =====================================

        stage('Verify Environment') {

            steps {

                sh '''
                    set -eu

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


        // =====================================
        // 3. AUTOMATED TESTING
        // =====================================

        stage('Run Tests') {

            steps {

                sh '''
                    set -eu

                    mkdir -p reports

                    docker run --rm \
                        --user "$(id -u):$(id -g)" \
                        -e APP_ENV=testing \
                        -e APP_DEBUG=false \
                        -e APP_TIMEZONE=Asia/Baghdad \
                        -e SECRET_KEY=ci-only-secret-key-32-characters-minimum-123 \
                        -e DATABASE_URL=sqlite+aiosqlite:///./test_ci.db \
                        -e SUPABASE_URL=https://mock-supabase.local \
                        -e SUPABASE_ANON_KEY=ci-placeholder \
                        -e SUPABASE_SERVICE_ROLE_KEY=ci-placeholder \
                        -e SUPABASE_STORAGE_BUCKET=lab-results \
                        -e FRONTEND_ORIGINS=http://localhost:3000 \
                        -v "$WORKSPACE:/workspace" \
                        -w /workspace \
                        python:3.12-slim \
                        sh -ec '

                            python -m venv /tmp/ci-venv

                            /tmp/ci-venv/bin/pip install \
                                --no-cache-dir \
                                -r requirements-dev.txt

                            /tmp/ci-venv/bin/python \
                                -m compileall -q app database

                            /tmp/ci-venv/bin/ruff check .

                            /tmp/ci-venv/bin/pytest \
                                -v \
                                --asyncio-mode=auto \
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


        // =====================================
        // 4. BUILD PRODUCTION IMAGE
        // =====================================

        stage('Build Docker Image') {

            steps {

                sh '''
                    set -eu

                    echo "Building production image: $NEW_IMAGE"

                    docker build \
                        --pull \
                        --label "org.opencontainers.image.revision=$GIT_SHA" \
                        --tag "$NEW_IMAGE" \
                        .

                    docker image inspect "$NEW_IMAGE" >/dev/null

                    echo "Docker image built successfully."
                '''
            }
        }


        // =====================================
        // 5. DEPLOY PRODUCTION
        // =====================================

        stage('Deploy Production') {

            steps {

                sh '''
                    set -Eeuo pipefail

                    # Copy Compose configuration to a stable server path
                    install -m 0644 \
                        "$WORKSPACE/compose.production.yaml" \
                        "$COMPOSE_FILE"

                    cd "$DEPLOY_DIR"

                    # Identify current running image
                    PREVIOUS_IMAGE="$(
                        docker inspect \
                        --format '{{.Config.Image}}' \
                        "$CONTAINER_NAME" 2>/dev/null || true
                    )"

                    # Validate Compose configuration
                    BACKEND_IMAGE="$NEW_IMAGE" docker compose \
                        -p "$COMPOSE_PROJECT" \
                        -f "$COMPOSE_FILE" \
                        config --quiet

                    # Rollback function
                    rollback() {

                        echo "Deployment failed. Restoring previous image."

                        if [ -n "$PREVIOUS_IMAGE" ]; then

                            BACKEND_IMAGE="$PREVIOUS_IMAGE" docker compose \
                                -p "$COMPOSE_PROJECT" \
                                -f "$COMPOSE_FILE" \
                                up -d --no-deps --force-recreate backend

                        else

                            docker compose \
                                -p "$COMPOSE_PROJECT" \
                                -f "$COMPOSE_FILE" \
                                stop backend || true

                            docker compose \
                                -p "$COMPOSE_PROJECT" \
                                -f "$COMPOSE_FILE" \
                                rm -f backend || true

                        fi
                    }

                    # Start new production container
                    if ! BACKEND_IMAGE="$NEW_IMAGE" docker compose \
                        -p "$COMPOSE_PROJECT" \
                        -f "$COMPOSE_FILE" \
                        up -d --no-deps --force-recreate backend; then

                        rollback

                        exit 1

                    fi

                    # Wait for Docker health status
                    HEALTHY=0

                    for attempt in $(seq 1 45); do

                        STATUS="$(
                            docker inspect \
                            --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' \
                            "$CONTAINER_NAME" 2>/dev/null || echo missing
                        )"

                        echo "Health check attempt $attempt: $STATUS"

                        if [ "$STATUS" = "healthy" ]; then

                            HEALTHY=1

                            break

                        fi

                        if [ "$STATUS" = "unhealthy" ] || \
                           [ "$STATUS" = "missing" ]; then

                            break

                        fi

                        sleep 2

                    done

                    # Rollback if health check failed
                    if [ "$HEALTHY" -ne 1 ]; then

                        echo "New release failed health verification."

                        rollback

                        exit 1

                    fi

                    # Save active image for future Compose commands
                    printf 'BACKEND_IMAGE=%s\\n' "$NEW_IMAGE" \
                        > "$DEPLOY_DIR/.env.next"

                    mv "$DEPLOY_DIR/.env.next" "$DEPLOY_DIR/.env"

                    echo "======================================"

                    echo "PRODUCTION DEPLOYMENT SUCCESSFUL"

                    echo "IMAGE: $NEW_IMAGE"

                    echo "CONTAINER: $CONTAINER_NAME"

                    echo "PORT: 8000"

                    echo "======================================"
                '''
            }
        }

    }

    post {

        success {

            echo 'CI/CD pipeline completed successfully.'

        }

        failure {

            echo 'CI/CD failed. Check Jenkins logs and Docker container status.'

        }

        always {

            echo 'Pipeline execution finished.'

        }
    }
}
