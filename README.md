# 🎫 NexusDesk: AI-Powered Support Ticketing System

**Live Production URL:** [http://nexusdesk-support.southeastasia.cloudapp.azure.com](http://nexusdesk-support.southeastasia.cloudapp.azure.com)

NexusDesk is a professional-grade, full-stack support platform built to bridge the gap between customers and support teams. It features a robust **Django REST API**, a high-performance **React (Vite)** frontend, and is fully containerized with **Docker** for cloud-native deployment on **Microsoft Azure**.

## 📸 Project Gallery

![Dashboard Screenshot](./screenshots/dashboard.png)
*Stats Dashboard rendering DB-aggregated metrics from PostgreSQL.*

![Create Ticket Screenshot](./screenshots/create_ticket.png)
*Ticket Creation form with LLM-powered auto-suggestions (Gemini) running in the background.*

## 🛠️ Tech Stack & Infrastructure

I containerized the entire application using **Docker & Docker Compose** to ensure seamless transitions between development and production.

* **Backend:** Django 5.x, Django REST Framework (DRF), WhiteNoise (Static Files)
* **Frontend:** React 18+ (Vite), Axios, CSS (Custom Blueprint Theme)
* **Database:** PostgreSQL (Production), SQLite (Development)
* **AI Integration:** Google Gemini 2.5 Flash via the `google-genai` SDK
* **Cloud & DevOps:** Microsoft Azure (Ubuntu VM), Azure DNS, Nginx, Google OAuth2

## ✨ Core Features

1. **AI Support Agent & Smart Categorization:** When a user describes a problem, the integrated **Gemini AI Support Agent** analyzes the text in real-time. It doesn't just categorize the ticket; it acts as a first-line responder by generating helpful, context-aware solution suggestions and pre-filling technical metadata like Priority and Category.
2. **Google OAuth2 Authentication:** Secure, one-tap login for users, fully configured for production environments via Azure DNS mapping.
3. **Role-Based Access Control (RBAC):** Custom `AccountAdapter` logic directs users to specific interfaces; Staff are routed to the **Admin Management Panel**, while users go to the **Customer Dashboard**.
4. **Database-Level Performance:** Dashboard statistics utilize Django ORM's `aggregate` and `annotate` functions to push heavy computations to PostgreSQL for maximum efficiency.
5. **Professional Cloud Deployment:** Hosted on an Azure Virtual Machine with a dedicated DNS label, ensuring a stable and professional public endpoint.

## 🧠 Design Decisions: The AI Agent Logic

For the AI integration, I chose **Google's Gemini 2.5 Flash**. I specifically selected it because:
* **Inference Speed:** Crucial for a fluid UI experience where the "Support Agent" provides suggestions while the user is still interacting with the form.
* **Instruction Following:** It natively supports strict JSON-mode outputs, ensuring the backend always receives a structured dictionary of categories and agent responses rather than messy conversational text.
* **Graceful Degradation:** If the AI service is unreachable, the system automatically falls back to manual entry mode, ensuring the core ticketing service remains 100% available.

## 🚀 Installation & Setup

### **Local Development**
1. **Clone the repository:**
   ```bash
   git clone [https://github.com/swatishah946/SupportTicketSystem.git](https://github.com/swatishah946/SupportTicketSystem.git)
   cd SupportTicketSystem

2. **Set up the Environment Variable:**
   Create a `.env` file in the root directory of the project and add your Google Gemini API key:
   ```env
     VITE_API_URL=http://localhost:8000/api
     GEMINI_API_KEY=your_api_key_here
     GOOGLE_CLIENT_ID=your_google_id
     SECRET_KEY=your_secure_django_key
   ```

3. **Build and Launch:**
Open your terminal in the root directory and run a single Docker command:
```bash
docker-compose up --build
```

