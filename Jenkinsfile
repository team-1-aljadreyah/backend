
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

            echo "======================================"
            echo "STARTING PRODUCTION DEPLOYMENT"
            echo "======================================"

            # 1. Copy production Compose configuration

            install -m 0644 \
                "$WORKSPACE/compose.production.yaml" \
                "$COMPOSE_FILE"

            cd "$DEPLOY_DIR"


            # 2. Detect previous running image

            PREVIOUS_IMAGE="$(
                docker inspect \
                    --format '{{.Config.Image}}' \
                    "$CONTAINER_NAME" 2>/dev/null || true
            )"

            echo "Previous image: ${PREVIOUS_IMAGE:-NONE}"
            echo "New image: $NEW_IMAGE"


            # 3. Validate Docker Compose configuration

            BACKEND_IMAGE="$NEW_IMAGE" docker compose \
                -p "$COMPOSE_PROJECT" \
                -f "$COMPOSE_FILE" \
                config --quiet


            # 4. Rollback function

            rollback() {

                echo "======================================"
                echo "STARTING ROLLBACK"
                echo "======================================"

                if [ -n "$PREVIOUS_IMAGE" ]; then

                    echo "Restoring previous image: $PREVIOUS_IMAGE"

                    BACKEND_IMAGE="$PREVIOUS_IMAGE" docker compose \
                        -p "$COMPOSE_PROJECT" \
                        -f "$COMPOSE_FILE" \
                        up -d --no-deps --force-recreate backend || {

                            echo "WARNING: Previous image restoration failed."
                            return 1
                        }

                else

                    echo "No previous image exists."
                    echo "Removing failed deployment container."

                    docker rm -f "$CONTAINER_NAME" \
                        >/dev/null 2>&1 || true

                fi

                echo "Rollback procedure finished."
            }


            # 5. Deploy new container

            echo "Starting new production container..."

            if ! BACKEND_IMAGE="$NEW_IMAGE" docker compose \
                -p "$COMPOSE_PROJECT" \
                -f "$COMPOSE_FILE" \
                up -d --no-deps --force-recreate backend; then

                echo "ERROR: Docker Compose deployment failed."

                docker logs --tail 200 "$CONTAINER_NAME" || true

                rollback || true

                exit 1

            fi


            # 6. Wait for Docker Health Check

            echo "Waiting for application readiness..."

            HEALTHY=0

            for attempt in $(seq 1 90); do

                STATUS="$(
                    docker inspect \
                        --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' \
                        "$CONTAINER_NAME" 2>/dev/null || echo missing
                )"

                STATE="$(
                    docker inspect \
                        --format '{{.State.Status}}' \
                        "$CONTAINER_NAME" 2>/dev/null || echo missing
                )"

                echo "Health attempt $attempt/90: $STATUS | Container: $STATE"


                if [ "$STATUS" = "healthy" ]; then

                    HEALTHY=1

                    echo "Application is healthy."

                    break

                fi


                if [ "$STATUS" = "unhealthy" ] || \
                   [ "$STATUS" = "missing" ] || \
                   [ "$STATUS" = "no-healthcheck" ] || \
                   [ "$STATE" = "exited" ] || \
                   [ "$STATE" = "dead" ]; then

                    echo "Application health verification failed."

                    break

                fi

                sleep 2

            done


            # 7. Handle failed health verification

            if [ "$HEALTHY" -ne 1 ]; then

                echo "======================================"
                echo "DEPLOYMENT HEALTH CHECK FAILED"
                echo "======================================"

                echo "Container state:"

                docker inspect \
                    --format '{{json .State}}' \
                    "$CONTAINER_NAME" || true

                echo "Health check details:"

                docker inspect \
                    --format '{{json .State.Health}}' \
                    "$CONTAINER_NAME" || true

                echo "Last 200 container log lines:"

                docker logs --tail 200 "$CONTAINER_NAME" || true

                rollback || true

                exit 1

            fi


            # 8. Save successfully deployed image

            echo "Saving active production image..."

            umask 077

            printf 'BACKEND_IMAGE=%s\n' "$NEW_IMAGE" \
                > "$DEPLOY_DIR/.env.next"

            mv "$DEPLOY_DIR/.env.next" "$DEPLOY_DIR/.env"


            # 9. Deployment success

            echo "======================================"
            echo "PRODUCTION DEPLOYMENT SUCCESSFUL"
            echo "======================================"

            echo "IMAGE: $NEW_IMAGE"
            echo "CONTAINER: $CONTAINER_NAME"
            echo "PORT: 8000"
            echo "HEALTH: HEALTHY"

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
