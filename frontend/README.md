# Autopsy.ai — Forensics Studio Frontend

The frontend interface for **autopsy.ai** is built with **Next.js 14 (App Router)**, **TypeScript**, and **Tailwind CSS**.

---

## 💻 Tech Stack & Key Libraries

- **Next.js 14 (App Router)**
- **React 18** & **TypeScript**
- **Tailwind CSS** with dark/light mode telemetry
- **Lucide React** for icons
- **Recharts** & **React Flow** for investigation visualizations

---

## 🚀 Quickstart

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure Environment (Optional)
If running against a remote backend or custom port, create `.env.local`:
```bash
cp .env.example .env.local
```
*(Default Next.js proxy rewrites `/api/*` requests to `http://127.0.0.1:8008` in development)*

### 3. Run Development Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 📦 Production Build

```bash
npm run build
npm run start
```
