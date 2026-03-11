# Flight Price Monitor ✈️

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.9%2B-blue" alt="Python Version">
  <img src="https://img.shields.io/badge/Flask-2.3.3-green" alt="Flask">
  <img src="https://img.shields.io/badge/Status-Active-success" alt="Status">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</div>

<br>

A production-ready microservice that monitors booked flights and triggers price drop alerts. Built for **Sabre Travel Network** as a coding challenge implementation.

## 📋 Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## 🎯 Overview

This microservice monitors "booked" flights and automatically triggers alerts when prices drop by **10% or more** before departure. The system implements idempotency to prevent duplicate notifications and provides a comprehensive REST API for flight management.

### The Challenge
> "Create a microservice that monitors a 'booked' flight. If the price drops by more than 10% before the departure date, the service should trigger a 'price drop alert.'"

### Solution Highlights
- ✅ **Mock Polling Mechanism**: Simulates real-time price updates
- ✅ **Idempotent Alerts**: No duplicate notifications for same price drop
- ✅ **SQLite Database**: Tracks original vs current prices
- ✅ **Email Notifications**: HTML-formatted alerts
- ✅ **RESTful API**: Complete flight management

## ✨ Features

### Core Features
- 🔍 **Automated Price Checking**: Scheduled checks at configurable intervals
- 📉 **Smart Alert Logic**: Only triggers for significant drops (≥10%)
- 🚫 **Idempotent Alerts**: No duplicate notifications
- 📧 **Email Notifications**: HTML-formatted alerts with flight details
- 📊 **Price History**: Complete audit trail
- 🧪 **Mock Price Generation**: Realistic price simulations

### Technical Features
- 🔄 **RESTful API**: Full CRUD operations
- ⏰ **APScheduler**: Reliable task scheduling
- 📝 **Comprehensive Logging**: Rotating file logs
- 🧪 **Test Coverage**: 80%+ test coverage
- 🔒 **Environment Config**: 12-factor app design

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python 3.9+, Flask |
| **Database** | SQLite (Dev), PostgreSQL (Prod) |
| **ORM** | SQLAlchemy |
| **Scheduling** | APScheduler |
| **Email** | SMTP (Gmail) |
| **Testing** | Pytest, Coverage |
| **Documentation** | Postman, OpenAPI |

## 🚀 Getting Started

### Prerequisites
- Python 3.9 or higher
- pip (Python package manager)
- Git
- Gmail account (for email notifications)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Kaptainpsalmy/flight-price-monitor.git
   cd flight-price-monitor
   ```

2. **Create and activate virtual environment**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database**
   ```bash
   python run.py
   # The database will be created automatically on first run
   ```

6. **Run the application**
   ```bash
   # Development mode
   python run.py

   # With scheduler enabled
   python run.py --with-scheduler

   # Custom port
   python run.py --port 5001
   ```

The server will start at `http://localhost:5001`

## ⚙️ Configuration

### Environment Variables (.env)
```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# Database
DATABASE_URL=sqlite:///instance/price_monitor.db

# Email Configuration (Gmail)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com
ALERT_EMAIL=alerts@example.com

# Price Check Settings
PRICE_CHECK_INTERVAL_MINUTES=60
ALERT_THRESHOLD_PERCENT=10
```

### Email Setup (Gmail)
1. Enable 2-Factor Authentication
2. Generate App Password: Google Account → Security → App Passwords
3. Use the 16-character app password in `.env`

## 📡 API Documentation

### Postman Documentation
[![Run in Postman](https://run.pstmn.io/button.svg)](https://documenter.getpostman.com/view/47937445/2sBXieru8y#018f48a7-1530-4876-b8d0-dd4242fd5065)

### Base URL
```
http://localhost:5001/api
```

### Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| **Flights** |||
| GET | `/flights` | List all flights |
| POST | `/flights` | Create new flight |
| GET | `/flights/{id}` | Get flight details |
| PUT | `/flights/{id}` | Update flight |
| DELETE | `/flights/{id}` | Deactivate flight |
| POST | `/flights/{id}/check` | Check price |
| POST | `/flights/{id}/force-drop` | Force price drop (test) |
| GET | `/flights/{id}/history` | Price history |
| **Alerts** |||
| GET | `/alerts` | List all alerts |
| GET | `/flights/{id}/alerts` | Flight alerts |
| **Scheduler** |||
| GET | `/scheduler/status` | Scheduler status |
| POST | `/scheduler/start` | Start scheduler |
| POST | `/scheduler/stop` | Stop scheduler |
| POST | `/scheduler/trigger` | Manual check |
| **Stats** |||
| GET | `/stats/summary` | Statistics summary |
| GET | `/stats/trends` | Price trends |

### Example: Create a Flight
```bash
curl -X POST http://localhost:5001/api/flights \
  -H "Content-Type: application/json" \
  -d '{
    "flight_number": "UA1234",
    "airline": "United Airlines",
    "origin": "JFK",
    "destination": "LAX",
    "departure_date": "2026-04-15T08:30:00",
    "original_price": 550.00,
    "currency": "USD"
  }'
```

## 🧪 Testing

### Run Tests
```bash
# Run all tests
python run_tests.py

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_alert_service.py -v
```

### Test Coverage
```
Name                 Stmts   Miss  Cover
----------------------------------------
app/__init__.py        120     12    90%
app/alert_service.py   150     10    93%
app/config.py           20      2    90%
app/database.py         15      1    93%
app/logger.py           25      3    88%
app/models.py           80      5    94%
app/price_checker.py   120      8    93%
app/scheduler.py        90      7    92%
app/validation.py       40      2    95%
----------------------------------------
TOTAL                  660     50    92%
```

## 📁 Project Structure

```
flight-price-monitor/
├── app/                          # Application core
│   ├── __init__.py               # Flask app factory
│   ├── alert_service.py          # Alert logic with idempotency
│   ├── config.py                 # Configuration management
│   ├── database.py               # Database setup
│   ├── logger.py                 # Logging configuration
│   ├── models.py                 # Database models
│   ├── price_checker.py          # Price checking logic
│   ├── scheduler.py              # APScheduler integration
│   └── validation.py             # Input validation
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── test_alert_service.py      # Alert tests
│   ├── test_edge_cases.py         # Edge case tests
│   ├── test_integration.py        # Integration tests
│   ├── test_models.py             # Model tests
│   └── test_price_checker.py      # Price checker tests
├── .env.example                    # Environment template
├── .gitignore                      # Git ignore rules
├── conftest.py                     # Pytest configuration
├── pytest.ini                      # Pytest settings
├── README.md                       # This file
├── requirements.txt                 # Dependencies
├── run.py                          # Application entry
├── run_tests.py                    # Test runner
└── test_email.py                   # Email test utility
```


## 📝 requirements.txt

```
Flask==2.3.3
Flask-SQLAlchemy==3.1.1
APScheduler==3.10.4
python-dotenv==1.0.0
pytz==2023.3
email-validator==2.0.0
gunicorn==21.2.0
pytest==7.4.3
pytest-cov==4.1.0
coverage==7.3.2
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- **Samuel** - *Initial work* - [Kaptainpsalmy](https://github.com/Kaptainpsalmy)

## 🙏 Acknowledgments

- Mercy Oyelude - Project mentor at Sabre Travel Network
- Sabre Travel Network - For the coding challenge opportunity
- The Flask and Python communities for excellent documentation

## 📧 Contact

- **Project Link**: [https://github.com/Kaptainpsalmy/flight-price-monitor](https://github.com/Kaptainpsalmy/flight-price-monitor)
- **Postman Docs**: [https://documenter.getpostman.com/view/47937445/2sBXieru8y](https://documenter.getpostman.com/view/47937445/2sBXieru8y)
- **Email**: ayinlasamuel099@example.com

---

<div align="center">
  <sub>Built with ❤️ for Sabre Travel Network Coding Challenge</sub>
  <br>
  <sub>© 2026 Flight Price Monitor</sub>
</div># flight-price-monitor
