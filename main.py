# main.py

import os
import re
import gradio as gr
import google.generativeai as genai
from dotenv import load_dotenv
from pypdf import PdfReader
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF
import time 

# --- SETUP AND CONFIGURATION ---

# Load environment variables from .env file
load_dotenv()

# Configure the Gemini API
try:
    genai.configure(api_key="key")
    GEMINI_MODEL = genai.GenerativeModel('gemini-2.5-pro')
    print("Gemini API configured successfully.")
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    # We will handle the case where the API key is missing in the app UI
    GEMINI_MODEL = None

# --- HELPER FUNCTIONS ---

def extract_text_from_pdf(pdf_file):
    """Extracts text from an uploaded PDF file."""
    if pdf_file is None:
        return ""
    try:
        pdf_reader = PdfReader(pdf_file.name)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        raise gr.Error(f"Failed to read PDF. It might be corrupted or password-protected. Error: {e}")

def fetch_url_content(url):
    """Fetches and cleans text content from a URL."""
    if not url:
        return ""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        # Remove script and style elements
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return ' '.join(text.split()) # Normalize whitespace
    except requests.RequestException as e:
        print(f"Warning: Could not fetch URL {url}. Error: {e}")
        return f"Could not fetch content from URL. Error: {e}"


def extract_info_from_jd(job_description):
    """Extracts Position Title and Company Name from the job description using simple regex."""
    position_match = re.search(r"(?i)(?:job\s+title|position|role):\s*([^\n]+)", job_description)
    position = position_match.group(1).strip() if position_match else "Position"

    company_match = re.search(r"(?i)(?:company|organization):\s*([^\n]+)", job_description)
    company = company_match.group(1).strip() if company_match else "Company"
    
    return position.replace(" ", "_"), company.replace(" ", "_")

def extract_applicant_name(resume_text):
    """Extracts the applicant's name from the resume text."""
    # A simple regex that looks for a capitalized name at the beginning of the text
    name_match = re.search(r"^([A-Z][a-z]+ [A-Z][a-z]+)", resume_text)
    if name_match:
        return name_match.group(1).strip().replace(" ", "_")
    return "Applicant"

def create_pdf_from_text(text, filename):
    """Creates a simple PDF file from a string of text, handling Unicode characters."""
    pdf = FPDF()
    pdf.add_page()
    # Use a standard, core font. Helvetica is a safe choice.
    pdf.set_font("Helvetica", size=11)
    
    # --- THIS IS THE CRITICAL FIX ---
    # Sanitize the text for PDF generation.
    # The 'latin-1' encoding is a standard for core PDF fonts.
    # 'replace' will substitute any unsupported character (like ♂ or emojis) with a '?'
    sanitized_text = text.encode('latin-1', 'replace').decode('latin-1')
    
    # Add multi-cell with the sanitized text
    pdf.multi_cell(0, 5, sanitized_text)
    
    pdf.output(filename)
    return filename

def sanitize_filename(text, max_length=50):
    """
    Sanitizes a string to be a valid filename.
    - Removes illegal characters.
    - Replaces spaces with underscores.
    - Truncates to a maximum length.
    """
    # Remove illegal characters for Windows filenames
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    # Replace spaces with underscores
    text = text.replace(" ", "_")
    # Truncate to a safe maximum length
    return text[:max_length].strip('_')

# --- CORE LOGIC ---

def generate_documents(resume_file, job_description, job_url):
    """The main function that orchestrates the document generation process."""
    if not GEMINI_MODEL:
        raise gr.Error("Gemini API key not configured. Please set the GEMINI_API_KEY in your .env file.")
        
    if resume_file is None:
        raise gr.Error("Please upload your resume to continue.")
    if not job_description.strip():
        raise gr.Error("Job description cannot be empty.")

    # 1. Process Inputs
    original_resume_text = extract_text_from_pdf(resume_file)
    url_content = fetch_url_content(job_url)
    
    # 2. Craft Prompts for Gemini
    # IMPORTANT: This prompt specifically instructs the AI not to change the structure.
    resume_prompt = f"""
    You are an expert ATS (Applicant Tracking System) resume optimizer. Your task is to rewrite the user's resume to be perfectly tailored for a specific job description.

    **CRITICAL INSTRUCTIONS:**
    1.  **DO NOT change the structure, layout, or section headers** of the original resume (e.g., 'Experience', 'Education', 'Skills', 'Projects').
    2.  **ONLY rewrite the text content** within each section (like bullet points, summaries, and descriptions).
    3.  Incorporate relevant keywords and phrases from the job description and the provided URL content naturally into the resume text.
    4.  Refine the language to be more professional and action-oriented. Quantify achievements where possible (e.g., "Increased efficiency by 20%").
    5.  Ensure the output is ONLY the full text of the modified resume. Do not add any extra comments, greetings, or explanations.

    ---
    **Original Resume Text:**
    {original_resume_text}
    ---
    **Job Description:**
    {job_description}
    ---
    **Content from Job/Company URL (for additional context):**
    {url_content}
    ---

    Now, provide the full, rewritten resume text.
    """

    cover_letter_prompt = f"""
    You are a professional career writer. Your task is to write a compelling and personalized cover letter for an applicant based on their resume and a specific job description.

    **INSTRUCTIONS:**
    1.  The tone should be professional, confident, and enthusiastic.
    2.  The cover letter should be concise, around 3-4 paragraphs.
    3.  Address it to the "Hiring Manager" if no specific name is available.
    4.  Highlight 2-3 key skills or experiences from the resume that directly match the requirements in the job description.
    5.  Mention the company name and position title from the job description.
    6.  The output should be ONLY the text of the cover letter.

    ---
    **Applicant's Resume Text:**
    {original_resume_text}
    ---
    **Job Description:**
    {job_description}
    ---
    **Content from Job/Company URL (for additional context):**
    {url_content}
    ---

    Now, write the cover letter.
    """

    # 3. Call Gemini API
    # NEW AND IMPROVED CODE
    # Make sure to add this at the top of your file!

    # ... inside the generate_documents function ...
    # OLD CODE
    try:
        print("Generating tailored resume...")
        resume_response = GEMINI_MODEL.generate_content(resume_prompt)
        new_resume_text = resume_response.text

        print("Generating cover letter...")
        cover_letter_response = GEMINI_MODEL.generate_content(cover_letter_prompt)
        cover_letter_text = cover_letter_response.text
    except Exception as e:
        raise gr.Error(f"An error occurred with the Gemini API: {e}")

    # 4. Prepare output files
    # NEW AND IMPROVED CODE
# 4. Prepare output files
    raw_applicant_name = extract_applicant_name(original_resume_text)
    raw_position_title, _ = extract_info_from_jd(job_description)

    # Sanitize the components for a safe filename
    applicant_name = sanitize_filename(raw_applicant_name)
    position_title = sanitize_filename(raw_position_title)

    # Handle case where sanitization might leave an empty string
    if not applicant_name: applicant_name = "Applicant"
    if not position_title: position_title = "Position"

    # Create filenames
    base_filename = f"{applicant_name}_{position_title}"
    resume_pdf_filename = f"{base_filename}_Resume.pdf"
    cover_letter_txt_filename = f"{base_filename}_Cover_Letter.txt"

    # Create a new, simple PDF from the generated resume text
    final_resume_pdf_path = create_pdf_from_text(new_resume_text, resume_pdf_filename)
    
    # Save the cover letter as a text file
    with open(cover_letter_txt_filename, "w", encoding="utf-8") as f:
        f.write(cover_letter_text)

    print("Documents generated successfully.")
    
    # 5. Return results to Gradio UI
    return (
        new_resume_text,          # Show new resume text in a textbox
        final_resume_pdf_path,    # Provide new resume as a downloadable file
        cover_letter_text,        # Show cover letter in a textbox
        cover_letter_txt_filename # Provide cover letter as a downloadable file
    )


# --- GRADIO UI ---

with gr.Blocks(theme=gr.themes.Soft(), title="AI Resume & Cover Letter Generator") as app:
    gr.Markdown(
        """
        # 🚀 AI-Powered Resume & Cover Letter Generator
        Tailor your application for any job in seconds. Upload your resume, paste the job details, and let Gemini craft the perfect documents for you.
        """
    )
    
    with gr.Accordion("⚠️ Important: Please Read Before Using", open=False):
        gr.Markdown(
            """
            ### How Formatting is Handled
            - **This tool focuses on perfecting the *content* of your resume for ATS scoring.** It rewrites the text to match the job description perfectly.
            - **It does NOT preserve the original visual design (fonts, colors, columns) of your PDF.** Directly editing a PDF's design is technically complex and unreliable.
            - **Best Practice:** After generating, **copy the new text** from the "Generated Resume Text" box below and **paste it into your original document** (e.g., your Word or Google Docs file) to maintain your personal branding and design.
            - The downloaded PDF is a clean, text-only version for your convenience.
            """
        )

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 1. Your Information")
            resume_file = gr.File(label="Upload Your Resume (PDF only)", file_types=[".pdf"])
            job_description = gr.Textbox(label="Paste the Full Job Description", lines=10, placeholder="Include company name and job title for best results...")
            job_url = gr.Textbox(label="Job Post or Company URL (Optional)", placeholder="https://careers.example.com/job/123")
            
            generate_button = gr.Button("✨ Generate Tailored Documents ✨", variant="primary")

        with gr.Column(scale=2):
            gr.Markdown("### 2. Your Generated Documents")
            with gr.Tabs():
                with gr.TabItem("📄 Generated Resume Text (Copy from here)"):
                    resume_output_text = gr.Textbox(
                        label="Optimized Resume Content", 
                        lines=20, 
                        interactive=False,
                        placeholder="Your new resume text will appear here..."
                    )
                with gr.TabItem("✉️ Generated Cover Letter"):
                    cover_letter_output_text = gr.Textbox(
                        label="Personalized Cover Letter", 
                        lines=20, 
                        interactive=False,
                        placeholder="Your new cover letter text will appear here..."
                    )
            
            gr.Markdown("### 3. Download Your Files")
            with gr.Row():
                download_resume_file = gr.File(label="Download Tailored Resume (PDF)", interactive=False)
                download_cover_letter_file = gr.File(label="Download Cover Letter (TXT)", interactive=False)

    # Connect the button to the function
    generate_button.click(
        fn=generate_documents,
        inputs=[resume_file, job_description, job_url],
        outputs=[resume_output_text, download_resume_file, cover_letter_output_text, download_cover_letter_file]
    )
    
    # gr.Examples(
    #     examples=[
    #         ["./resume_example.pdf", "Job Title: Senior Software Engineer\nCompany: Tech Innovations Inc.\nWe are looking for a Python expert with experience in cloud services (AWS/GCP) and a passion for building scalable systems.", "https://techinnovations.com/careers"]
    #     ],
    #     inputs=[resume_file, job_description, job_url],
    #     fn=generate_documents,
    #     cache_examples=False, # Set to True for faster demo, False for production
    #     label="Example (requires a local 'resume_example.pdf')"
    # )

if __name__ == "__main__":
    app.launch(debug=True)
