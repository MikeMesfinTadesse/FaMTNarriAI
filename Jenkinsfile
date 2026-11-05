pipeline {
  agent any
  stages {
    stage('Setup') {
      steps {
        sh 'python3 -m venv .venv'
        sh '.venv/bin/pip install --quiet --upgrade pip'
        sh '.venv/bin/pip install --quiet -r requirements.txt'
      }
    }
    stage('Test') {
      steps {
        sh '.venv/bin/pytest tests --junitxml=junit.xml --cov=api --cov=core --cov-report=xml'
      }
    }
  }
  post {
    always {
      junit allowEmptyResults: true, testResults: 'junit.xml'
    }
  }
}
