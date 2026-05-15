# Veriphy Backend API

A production-grade SMS verification backend built with FastAPI, designed for fintech applications. This backend provides secure merchant onboarding and SMS verification services with enterprise-grade security, scalability, and reliability.

## 🚀 Features

- **Merchant Onboarding**: Secure registration and management of merchant accounts
- **SMS Verification**: Robust SMS-based identity verification with fraud detection
- **JWT Authentication**: Secure token-based authentication system
- **PII Encryption**: Military-grade encryption for sensitive personal data
- **Clean Architecture**: Domain-Driven Design (DDD) with clear separation of concerns
- **Async Operations**: High-performance async/await throughout the stack
- **Background Jobs**: Celery-powered task processing for scalability
- **Comprehensive Testing**: Full test coverage with pytest and async support

## 🛠️ Tech Stack

- **Framework**: FastAPI (async Python web framework)
- **Database**: PostgreSQL with SQLAlchemy 2.0 (async ORM)
- **Cache**: Redis for session management and rate limiting
- **Task Queue**: Celery for background job processing
- **Security**: Jose (JWT), Cryptography (encryption), Argon2 (password hashing)
- **Validation**: Pydantic v2 with strict type checking
- **Migration**: Alembic for database schema management
- **Logging**: Structlog for structured logging
- **Testing**: Pytest with HTTPX for API testing

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.13+**: Download from [python.org](https://python.org)
- **PostgreSQL 15+**: Database server
- **Redis 7+**: In-memory data store
- **Git**: Version control system

### Installing Prerequisites on Ubuntu/Debian

```bash
# Update package list
sudo apt update

# Install Python 3.13 (if not already installed)
sudo apt install python3.13 python3.13-venv

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Install Redis
sudo apt install redis-server

# Start services
sudo systemctl start postgresql
sudo systemctl start redis-server
sudo systemctl enable postgresql
sudo systemctl enable redis-server
```

### Installing Prerequisites on macOS

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.13
brew install python@3.13

# Install PostgreSQL
brew install postgresql
brew services start postgresql

# Install Redis
brew install redis
brew services start redis
```

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/ahmad-cod/veriphy-be.git
cd veriphy-be
```

### 2. Set Up Python Virtual Environment

```bash
# Create virtual environment
python3.13 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Copy the example environment file and configure it:

```bash
cp .env.example .env  # If .env.example exists, otherwise create .env
```

Edit `.env` with your configuration:

```env
# === SYSTEM CONFIG ===
PROJECT_NAME="Veriphy API"
VERSION="1.0.0"
ENVIRONMENT="local"

# === INFRASTRUCTURE ===
DATABASE_URL="postgresql+asyncpg://postgres:your_password@localhost:5432/veriphy"
REDIS_URL="redis://localhost:6379/0"

# === SECURITY & AUTH ===
JWT_SECRET_KEY="your_super_secret_random_hex_string_here"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=60
BVN_HASH_PEPPER="your_bvn_hash_pepper_here"
SMS_HMAC_SECRET="your_sms_hmac_secret_here"
LOCAL_DEK="X7tN4VpQnJUUHdhenz7R0coO7D7z1f6Wf5DvyJzyy0c="

# === EXTERNAL INTEGRATIONS ===
SQUAD_API_URL="https://sandbox-api-d.squadco.com"
SQUAD_SECRET_KEY="your_squad_api_key_here"
```

**Important Security Notes:**

- Generate secure random strings for `JWT_SECRET_KEY` and `BVN_HASH_PEPPER`
- Use different values for development, staging, and production
- Never commit real secrets to version control

### 5. Set Up PostgreSQL Database

```bash
# Create database (adjust username/password as needed)
sudo -u postgres psql
```

```sql
CREATE DATABASE veriphy;
CREATE USER veriphy_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE veriphy TO veriphy_user;
\q
```

Update your `.env` file with the correct database URL:

```env
DATABASE_URL="postgresql+asyncpg://veriphy_user:your_secure_password@localhost:5432/veriphy"
```

### 6. Run Database Migrations

```bash
# Apply database migrations
alembic upgrade head
```

### 7. Start the Application

```bash
# Start the FastAPI server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: http://localhost:8000

## 🐳 Docker

This project includes Docker support for local development.

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Build and start the stack:

```bash
docker compose up --build
```

3. Run database migrations once the database is ready:

```bash
docker compose run --rm web alembic upgrade head
```

4. Open the API in your browser:

```bash
http://localhost:8000
```

> If you want to stop the local stack:
>
> ```bash
> docker compose down
> ```

````

## 🧪 Testing

### Run Unit Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_crypto.py -v
````

### API Testing

1. **Interactive API Documentation**: Visit http://localhost:8000/docs
2. **Alternative Documentation**: Visit http://localhost:8000/redoc

### Manual Testing with curl

```bash
# Health check
curl http://localhost:8000/health

# Get API documentation
curl http://localhost:8000/openapi.json
```

## 📁 Project Structure

```
veriphy-be/
├── src/
│   ├── main.py                 # FastAPI application factory
│   ├── core/
│   │   ├── config.py          # Application configuration
│   │   ├── security.py        # JWT and authentication
│   │   └── exceptions.py      # Custom exception handlers
│   ├── api/
│   │   ├── dependencies.py    # FastAPI dependencies
│   │   └── v1/
│   │       └── routers/       # API route handlers
│   ├── domain/
│   │   ├── models.py          # Database models
│   │   ├── crypto.py          # Encryption services
│   │   └── services/          # Business logic
│   ├── infrastructure/
│   │   ├── database.py        # Database connection
│   │   └── redis.py           # Redis connection
│   └── worker/
│       └── tasks.py           # Celery background tasks
├── tests/                     # Test suite
├── alembic/                   # Database migrations
├── requirements.txt           # Python dependencies
├── alembic.ini               # Alembic configuration
└── .env                      # Environment variables
```

## 🔧 Development Workflow

### Adding New Features

1. **Create a feature branch**:

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Write tests first** (TDD approach):

   ```bash
   # Add tests in tests/ directory
   pytest tests/ -v
   ```

3. **Implement the feature** following Clean Architecture principles

4. **Run full test suite**:

   ```bash
   pytest tests/ --cov=src
   ```

5. **Update documentation** if needed

### Database Changes

When making database schema changes:

```bash
# Generate migration
alembic revision --autogenerate -m "description of changes"

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

## 🔒 Security Features

- **JWT Authentication**: Stateless token-based auth
- **PII Encryption**: AES encryption for sensitive data
- **HMAC Hashing**: Secure hashing for BVN and SMS data
- **Rate Limiting**: Redis-based request rate limiting
- **CORS Protection**: Configurable cross-origin policies
- **Input Validation**: Strict Pydantic validation
- **SQL Injection Protection**: SQLAlchemy ORM safeguards

## 📊 Monitoring & Observability

- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Health Checks**: `/health` endpoint for monitoring
- **Performance Metrics**: Built-in FastAPI metrics
- **Error Tracking**: Comprehensive error handling and logging

## 🚀 Deployment

### Production Checklist

- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Use strong, randomly generated secrets
- [ ] Configure production database credentials
- [ ] Set up Redis cluster for high availability
- [ ] Configure Celery with message broker (Redis/RabbitMQ)
- [ ] Set up monitoring and alerting
- [ ] Configure SSL/TLS certificates
- [ ] Set up load balancer and reverse proxy

### Docker Deployment (Future)

```dockerfile
# Example Dockerfile for production
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Standards

- Follow PEP 8 style guidelines
- Use type hints for all function parameters and return values
- Write comprehensive docstrings
- Maintain test coverage above 80%
- Use meaningful commit messages

## 📝 API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## 🐛 Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'src'"**

```bash
# Set Python path
export PYTHONPATH=.
```

**"Connection refused" for PostgreSQL/Redis**

```bash
# Check if services are running
sudo systemctl status postgresql
sudo systemctl status redis-server

# Start services if needed
sudo systemctl start postgresql
sudo systemctl start redis-server
```

**"Permission denied" for database**

```bash
# Connect as postgres user and grant permissions
sudo -u postgres psql
GRANT ALL PRIVILEGES ON DATABASE veriphy TO veriphy_user;
```

**Tests failing with import errors**

```bash
# Run tests with proper path
PYTHONPATH=. pytest tests/ -v
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

For questions or support:

- Create an issue on GitHub
- Check the troubleshooting section above
- Review the API documentation

---

**Happy coding! 🚀**
