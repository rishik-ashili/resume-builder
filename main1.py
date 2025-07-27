# enhanced_main.py

import os
import re
import gradio as gr
import google.generativeai as genai
from dotenv import load_dotenv
from pypdf import PdfReader
import requests
from bs4 import BeautifulSoup
import subprocess
import tempfile
import shutil
import time
from pathlib import Path

# --- SETUP AND CONFIGURATION ---

# Load environment variables from .env file
load_dotenv()

# Configure the Gemini API
try:
    # Replace with your actual API key or use environment variable
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", "key"))
    GEMINI_MODEL = genai.GenerativeModel('gemini-2.0-flash-exp')
    print("Gemini API configured successfully.")
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
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
        raise gr.Error(f"Failed to read PDF. Error: {e}")

def fetch_url_content(url):
    """Fetches and cleans text content from a URL."""
    if not url:
        return ""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()
        
        text = soup.get_text(separator=' ', strip=True)
        return ' '.join(text.split())
    except requests.RequestException as e:
        print(f"Warning: Could not fetch URL {url}. Error: {e}")
        return f"Could not fetch content from URL. Error: {e}"

def extract_info_from_jd(job_description):
    """Extracts Position Title and Company Name from the job description."""
    # Try multiple patterns for position
    position_patterns = [
        r"(?i)(?:job\s+title|position|role|title)[:]\s*([^\n]+)",
        r"(?i)(?:looking\s+for|seeking|hiring)[\s\w]*?([A-Z][^,\n.]+(?:engineer|developer|manager|analyst|specialist|coordinator|assistant|director))",
        r"(?i)^([A-Z][^,\n.]+(?:engineer|developer|manager|analyst|specialist|coordinator|assistant|director))"
    ]
    
    position = "Position"
    for pattern in position_patterns:
        match = re.search(pattern, job_description)
        if match:
            position = match.group(1).strip()
            break
    
    # Try multiple patterns for company
    company_patterns = [
        r"(?i)(?:company|organization|at)[:]\s*([^\n]+)",
        r"(?i)(?:join|work\s+at|career\s+at)\s+([A-Z][^\n,.!?]+)",
        r"([A-Z][a-zA-Z\s&]+(?:Inc|LLC|Corp|Ltd|Company|Technologies|Solutions|Systems))"
    ]
    
    company = "Company"
    for pattern in company_patterns:
        match = re.search(pattern, job_description)
        if match:
            company = match.group(1).strip()
            break
    
    return sanitize_filename(position), sanitize_filename(company)

def extract_applicant_name_from_latex(latex_content):
    """Extracts the applicant's name from LaTeX content."""
    # Look for common name patterns in LaTeX resumes
    patterns = [
        r"\\name\{([^}]+)\}",
        r"\\author\{([^}]+)\}",
        r"\\begin\{center\}\s*\{\\[^}]*\}\s*([A-Z][a-z]+\s+[A-Z][a-z]+)",
        r"\\textbf\{([A-Z][a-z]+\s+[A-Z][a-z]+)\}",
        r"\\Large\s*([A-Z][a-z]+\s+[A-Z][a-z]+)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, latex_content)
        if match:
            return sanitize_filename(match.group(1).strip())
    
    return "Applicant"

def sanitize_filename(text, max_length=30):
    """Sanitizes a string to be a valid filename."""
    # Remove LaTeX commands and special characters
    text = re.sub(r'\\[a-zA-Z]+\{?', '', text)
    text = re.sub(r'[{}\\/*?:"<>|]', '', text)
    text = text.replace(' ', '_')
    return text[:max_length].strip('_')

def compile_latex_to_pdf(latex_content, output_filename):
    """Compiles LaTeX content to PDF using pdflatex."""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write LaTeX content to temporary file
            tex_file = os.path.join(temp_dir, "document.tex")
            with open(tex_file, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            # Compile LaTeX to PDF
            result = subprocess.run([
                'pdflatex', 
                '-interaction=nonstopmode',
                '-output-directory', temp_dir,
                tex_file
            ], capture_output=True, text=True, cwd=temp_dir)
            
            if result.returncode != 0:
                # Try again in case of citation/reference issues
                subprocess.run([
                    'pdflatex', 
                    '-interaction=nonstopmode',
                    '-output-directory', temp_dir,
                    tex_file
                ], capture_output=True, text=True, cwd=temp_dir)
            
            # Copy the generated PDF to the desired location
            pdf_file = os.path.join(temp_dir, "document.pdf")
            if os.path.exists(pdf_file):
                shutil.copy2(pdf_file, output_filename)
                return output_filename
            else:
                raise Exception(f"PDF compilation failed. LaTeX output: {result.stdout}\nErrors: {result.stderr}")
                
    except FileNotFoundError:
        raise gr.Error("pdflatex not found. Please install LaTeX (TeX Live, MikTeX, or MacTeX) on your system.")
    except Exception as e:
        raise gr.Error(f"LaTeX compilation failed: {str(e)}")

def generate_cover_letter_latex(applicant_name, position, company):
    """Generates a LaTeX template for cover letter matching resume style."""
    return f"""\\documentclass[11pt,a4paper,sans]{{moderncv}}

\\moderncvstyle{{casual}}
\\moderncvcolor{{blue}}

\\usepackage[scale=0.75]{{geometry}}

\\name{{{applicant_name}}}{{}}
\\title{{Cover Letter}}
\\address{{Your Address}}{{City, State ZIP}}{{Country}}
\\phone[mobile]{{+1~(555)~123~4567}}
\\email{{your.email@example.com}}

\\begin{{document}}

\\recipient{{Hiring Manager}}{{{company}\\\\Address}}
\\date{{\\today}}
\\opening{{Dear Hiring Manager,}}
\\closing{{Sincerely,}}

\\makelettertitle

[COVER_LETTER_CONTENT]

\\makeletterclosing

\\end{{document}}"""

# --- CORE LOGIC ---

def generate_documents_latex(resume_latex, job_description, job_url):
    """Generates tailored resume and cover letter from LaTeX input."""
    
    if not GEMINI_MODEL:
        raise gr.Error("Gemini API key not configured. Please set GEMINI_API_KEY in your .env file.")
        
    if not resume_latex.strip():
        raise gr.Error("Please provide your resume LaTeX code.")
    if not job_description.strip():
        raise gr.Error("Job description cannot be empty.")

    # Fetch URL content
    url_content = fetch_url_content(job_url)
    
    # Extract information for file naming
    applicant_name = extract_applicant_name_from_latex(resume_latex)
    position_title, company_name = extract_info_from_jd(job_description)
    
    # Create the enhanced resume prompt
    resume_prompt = f"""
You are an expert ATS resume optimizer. You will receive LaTeX code for a resume and must modify ONLY the text content to perfectly match a job description while maintaining the exact LaTeX structure, formatting, and commands.

**CRITICAL INSTRUCTIONS:**
1. **PRESERVE ALL LaTeX structure**: Keep all \\commands, {{braces}}, environments, spacing, and formatting EXACTLY as they are
2. **ONLY modify text content**: Change job descriptions, skills, achievements, project descriptions, and other text content
3. **Optimize for ATS**: Include relevant keywords from the job description naturally in the text
4. **Enhance language**: Make descriptions more professional, action-oriented, and quantified
5. **Match job requirements**: Align skills and experiences with the job requirements
6. **Output ONLY the complete modified LaTeX code**: No explanations, comments, or extra text

**Original Resume LaTeX:**
{resume_latex}

**Job Description:**
{job_description}

**Company/URL Content:**
{url_content}

Provide the complete modified LaTeX code:
"""

    # Create cover letter prompt
    cover_letter_prompt = f"""
Write a professional cover letter for the following job application. The cover letter should be 3-4 paragraphs, professional yet personable, and highlight relevant skills from the resume.

**Resume Content (for reference):**
{resume_latex}

**Job Description:**
{job_description}

**Company/URL Content:**
{url_content}

**Requirements:**
- Address to "Hiring Manager" 
- Mention company name: {company_name}
- Mention position: {position_title}
- Professional and enthusiastic tone
- Highlight 2-3 key relevant qualifications
- Output ONLY the cover letter text content (no LaTeX formatting)

Write the cover letter:
"""

    try:
        print("Generating optimized resume...")
        resume_response = GEMINI_MODEL.generate_content(resume_prompt)
        optimized_latex = resume_response.text.strip()
        
        # Clean up the response (remove markdown code blocks if present)
        if optimized_latex.startswith('```'):
            optimized_latex = re.sub(r'^```(?:latex)?\n?', '', optimized_latex)
            optimized_latex = re.sub(r'\n?```$', '', optimized_latex)
        
        print("Generating cover letter...")
        cover_letter_response = GEMINI_MODEL.generate_content(cover_letter_prompt)
        cover_letter_content = cover_letter_response.text.strip()
        
    except Exception as e:
        raise gr.Error(f"Error with Gemini API: {str(e)}")

    # Create filenames
    base_filename = f"{applicant_name}_{position_title}"
    resume_pdf_filename = f"{base_filename}_Resume.pdf"
    cover_letter_filename = f"{base_filename}_Cover_Letter.pdf"
    
    try:
        # Compile optimized resume to PDF
        print("Compiling resume PDF...")
        compile_latex_to_pdf(optimized_latex, resume_pdf_filename)
        
        # Create cover letter LaTeX and compile
        print("Creating cover letter PDF...")
        cover_letter_latex = generate_cover_letter_latex(applicant_name, position_title, company_name)
        cover_letter_latex = cover_letter_latex.replace('[COVER_LETTER_CONTENT]', cover_letter_content)
        compile_latex_to_pdf(cover_letter_latex, cover_letter_filename)
        
    except Exception as e:
        raise gr.Error(f"PDF compilation error: {str(e)}")

    print("Documents generated successfully.")
    
    return (
        optimized_latex,           # Show optimized LaTeX code
        resume_pdf_filename,       # Resume PDF download
        cover_letter_content,      # Show cover letter text
        cover_letter_filename,     # Cover letter PDF download
        cover_letter_latex         # Show cover letter LaTeX code
    )

def generate_documents_pdf(resume_pdf, job_description, job_url):
    """Generates documents from PDF input (legacy support)."""
    
    if not GEMINI_MODEL:
        raise gr.Error("Gemini API key not configured.")
        
    if resume_pdf is None:
        raise gr.Error("Please upload your resume PDF.")
    if not job_description.strip():
        raise gr.Error("Job description cannot be empty.")

    # Extract text from PDF
    resume_text = extract_text_from_pdf(resume_pdf)
    url_content = fetch_url_content(job_url)
    
    # Use text-based optimization (your original approach)
    resume_prompt = f"""
Rewrite this resume to be perfectly optimized for the given job description. Focus on:
1. Including relevant keywords naturally
2. Quantifying achievements
3. Using action-oriented language  
4. Matching job requirements
5. Professional tone throughout

**Original Resume:**
{resume_text}

**Job Description:**
{job_description}

**Company Info:**
{url_content}

Provide the complete optimized resume text:
"""

    cover_letter_prompt = f"""
Write a professional cover letter based on the resume and job description.

**Resume:**
{resume_text}

**Job Description:**
{job_description}

**Company Info:**
{url_content}

Write a compelling 3-4 paragraph cover letter:
"""

    try:
        resume_response = GEMINI_MODEL.generate_content(resume_prompt)
        optimized_text = resume_response.text
        
        cover_letter_response = GEMINI_MODEL.generate_content(cover_letter_prompt)
        cover_letter_text = cover_letter_response.text
        
        # Create simple PDFs (your original method)
        from fpdf import FPDF
        
        def create_simple_pdf(text, filename):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=11)
            # Handle encoding issues
            sanitized_text = text.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 5, sanitized_text)
            pdf.output(filename)
            return filename
        
        # Extract names for filenames
        position_title, company_name = extract_info_from_jd(job_description)
        name_match = re.search(r'^([A-Z][a-z]+ [A-Z][a-z]+)', resume_text)
        applicant_name = sanitize_filename(name_match.group(1)) if name_match else "Applicant"
        
        base_filename = f"{applicant_name}_{position_title}"
        resume_pdf_filename = f"{base_filename}_Resume.pdf"
        cover_letter_pdf_filename = f"{base_filename}_Cover_Letter.pdf"
        
        create_simple_pdf(optimized_text, resume_pdf_filename)
        create_simple_pdf(cover_letter_text, cover_letter_pdf_filename)
        
        return (
            optimized_text,
            resume_pdf_filename,
            cover_letter_text,
            cover_letter_pdf_filename,
            ""  # No LaTeX output for PDF input
        )
        
    except Exception as e:
        raise gr.Error(f"Error generating documents: {str(e)}")

# --- GRADIO UI ---

def create_ui():
    with gr.Blocks(theme=gr.themes.Soft(), title="AI Resume & Cover Letter Generator") as app:
        gr.Markdown("""
        # 🚀 AI-Powered Resume & Cover Letter Generator
        
        **NEW: LaTeX Support for Perfect Formatting!** 
        
        Upload your LaTeX resume code to maintain exact formatting, fonts, colors, and structure while optimizing content for ATS systems.
        """)
        
        with gr.Accordion("📖 How to Use This Tool", open=False):
            gr.Markdown("""
            ### Method 1: LaTeX Input (Recommended)
            - **Best Results**: Paste your resume's LaTeX code for perfect formatting preservation
            - **Perfect ATS Optimization**: Content will be optimized while maintaining your exact design
            - **Professional Output**: Generated PDFs match your original styling exactly
            
            ### Method 2: PDF Upload (Basic)
            - Upload your PDF resume for basic text optimization
            - **Note**: Original formatting will be lost, but content will be ATS-optimized
            
            ### Requirements
            - LaTeX installation (TeX Live, MikTeX, or MacTeX) required for LaTeX compilation
            - Job description with company name and position for best results
            """)
        
        with gr.Tabs():
            # LaTeX Input Tab
            with gr.TabItem("📝 LaTeX Input (Recommended)"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Input Your Information")
                        
                        resume_latex_input = gr.Textbox(
                            label="Paste Your Resume LaTeX Code",
                            lines=15,
                            placeholder="\\documentclass{article}\n\\begin{document}\n...\n\\end{document}",
                            info="Paste the complete LaTeX code of your resume"
                        )
                        
                        job_description_latex = gr.Textbox(
                            label="Job Description", 
                            lines=8,
                            placeholder="Include company name, position title, and requirements..."
                        )
                        
                        job_url_latex = gr.Textbox(
                            label="Job Post URL (Optional)",
                            placeholder="https://company.com/careers/job-123"
                        )
                        
                        generate_latex_btn = gr.Button(
                            "✨ Generate Optimized Documents", 
                            variant="primary",
                            size="lg"
                        )
                    
                    with gr.Column(scale=1):
                        gr.Markdown("### Generated Content")
                        
                        with gr.Tabs():
                            with gr.TabItem("📄 Optimized Resume LaTeX"):
                                resume_latex_output = gr.Textbox(
                                    label="Optimized LaTeX Code",
                                    lines=12,
                                    interactive=True,
                                    info="You can edit this code before downloading"
                                )
                            
                            with gr.TabItem("✉️ Cover Letter"):
                                cover_letter_output = gr.Textbox(
                                    label="Cover Letter Content",
                                    lines=12,
                                    interactive=False
                                )
                            
                            with gr.TabItem("📄 Cover Letter LaTeX"):
                                cover_letter_latex_output = gr.Textbox(
                                    label="Cover Letter LaTeX Code",
                                    lines=12,
                                    interactive=True
                                )
            
            # PDF Input Tab  
            with gr.TabItem("📎 PDF Upload (Basic)"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Upload Your Resume")
                        
                        resume_pdf_input = gr.File(
                            label="Upload Resume PDF",
                            file_types=[".pdf"]
                        )
                        
                        job_description_pdf = gr.Textbox(
                            label="Job Description",
                            lines=8,
                            placeholder="Include company name, position title, and requirements..."
                        )
                        
                        job_url_pdf = gr.Textbox(
                            label="Job Post URL (Optional)",
                            placeholder="https://company.com/careers/job-123"
                        )
                        
                        generate_pdf_btn = gr.Button(
                            "🔧 Generate Basic Documents",
                            variant="secondary"
                        )
                    
                    with gr.Column(scale=1):
                        gr.Markdown("### Generated Content")
                        
                        resume_text_output = gr.Textbox(
                            label="Optimized Resume Text",
                            lines=15,
                            interactive=False
                        )
                        
                        cover_letter_text_output = gr.Textbox(
                            label="Cover Letter Text", 
                            lines=10,
                            interactive=False
                        )
        
        # Download Section
        gr.Markdown("### 📥 Download Your Documents")
        with gr.Row():
            resume_download = gr.File(label="📄 Download Resume PDF", interactive=False)
            cover_letter_download = gr.File(label="✉️ Download Cover Letter PDF", interactive=False)
        
        # Event handlers
        generate_latex_btn.click(
            fn=generate_documents_latex,
            inputs=[resume_latex_input, job_description_latex, job_url_latex],
            outputs=[
                resume_latex_output, 
                resume_download, 
                cover_letter_output, 
                cover_letter_download,
                cover_letter_latex_output
            ]
        )
        
        generate_pdf_btn.click(
            fn=generate_documents_pdf,
            inputs=[resume_pdf_input, job_description_pdf, job_url_pdf],
            outputs=[
                resume_text_output,
                resume_download,
                cover_letter_text_output, 
                cover_letter_download,
                gr.Textbox(visible=False)  # Placeholder for LaTeX output
            ]
        )
    
    return app

if __name__ == "__main__":
    app = create_ui()
    app.launch(
        debug=True,
        share=False,
    )
