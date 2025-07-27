# 🚀 AI-Powered Resume & Cover Letter Generator


This is a web application built with Gradio and Python that uses the Google Gemini API to tailor a resume and generate a cover letter for a specific job application.

The tool helps you optimize your resume's content to achieve a high ATS (Applicant Tracking System) score by aligning it with the keywords and requirements of a job description.




## Features

-   **Upload Your Resume:** Accepts your existing resume in PDF format.
-   **Job Description Input:** Provide the job description and an optional URL for context.
-   **AI-Powered Content Generation:**
    -   Rewrites your resume's text to be perfectly tailored for the job.
    -   Generates a compelling, personalized cover letter.
-   **Structure Preservation:** The AI is specifically instructed **not** to change the section headers or layout of your resume, focusing only on improving the text content.
-   **Downloadable Files:** Provides the generated documents as downloadable files (`.pdf` for the resume, `.txt` for the cover letter).
-   **Smart File Naming:** Automatically names the downloaded files based on the applicant's name and position title (e.g., `John_Doe_Software_Engineer_Resume.pdf`).

## ⚠️ Important Note on PDF Formatting

This tool is designed to perfect the **content** of your resume, not its visual design.

-   **It does NOT preserve the original fonts, colors, or complex layouts** of your uploaded PDF. Directly editing and preserving the style of a PDF is technically complex and unreliable.
-   The downloaded resume is a clean, text-only PDF generated from the AI's output.

### Recommended Workflow
1.  Generate the new resume text using this application.
2.  **Copy the optimized text** from the "Generated Resume Text" box in the UI.
3.  **Paste this new text into your original document file** (e.g., your Microsoft Word, Google Docs, or LaTeX file).
4.  Save and export your beautifully formatted document with ATS-optimized content.

## Tech Stack

-   **Backend:** Python
-   **Web UI:** Gradio
-   **AI Model:** Google Gemini API (`google-generativeai`)
-   **PDF Reading:** `pypdf`
-   **PDF Creation:** `fpdf2`
-   **Web Scraping:** `requests`, `BeautifulSoup4`

## Setup and Installation

Follow these steps to run the application on your local machine.

### 1. Prerequisites
-   Python 3.8+
-   Git
-   A **Google Gemini API Key**. You can get one for free from [Google AI Studio](https://aistudio.google.com/app/apikey).

### 2. Clone the Repository
Open your terminal and clone the project repository:
```bash
git clone <your-repository-url>
cd resume-builder
```

### 3. Create a Virtual Environment (Recommended)
It's best practice to create a virtual environment to manage project dependencies.

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

### 4. Install Dependencies
Install all the required Python packages using the `requirements.txt` file:
```bash
pip install -r requirements.txt
```

### 5. Configure Your API Key
You must provide your Gemini API key using an environment variable for security.

1.  Create a new file named `.env` in the root of the project directory.
2.  Add the following line to the `.env` file, replacing `YOUR_API_KEY_HERE` with your actual key:
    ```
    GEMINI_API_KEY="YOUR_API_KEY_HERE"
    ```
The `.env` file is listed in `.gitignore`, so your secret key will not be accidentally committed to source control.

## How to Run the Application

Once the setup is complete, run the main Python script from your terminal:
```bash
python main.py
```
The application will start, and you will see a local URL in your terminal (usually `http://127.0.0.1:7860`). Open this URL in your web browser to use the application.

## Troubleshooting

-   **`429 You exceeded your current quota` Error:** This means you've hit the rate limit of the Gemini API's free tier.
    -   **Solution 1:** Wait for a minute before trying again.
    -   **Solution 2 (Recommended):** In `main.py`, change the model from `gemini-1.5-pro-latest` to `gemini-1.0-pro`, which has a much more generous free tier (60 requests per minute).

-   **`OSError: [Errno 22] Invalid argument`:** This usually means the generated filename is too long or contains illegal characters. The latest version of `main.py` includes a `sanitize_filename` function to prevent this. Ensure your code includes this fix.

-   **`FPDFUnicodeEncodingException`:** This happens if the text contains special characters (like LaTeX symbols or emojis) that the default PDF font doesn't support. The latest code sanitizes the text before PDF creation to prevent this crash.

---
