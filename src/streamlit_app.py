import streamlit as st
from dspy import LM
from fpdf import FPDF
from datetime import datetime
import os

os.environ['OPENAI_API_KEY'] = st.secrets['OPENAI_API_KEY']
# Initialize the LM model
api_key = st.secrets['OPENAI_API_KEY']
lm = LM(model="gemini/gemini-1.5-flash-latest", api_key=api_key)

class ApplicationPDF(FPDF):
    def header(self):
        self.set_font("Arial", size=10)
        current_date = datetime.now().strftime("%d-%m-%Y")
        self.cell(0, 5, f"Date: {current_date}", align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def add_body(self, content):
        self.set_font("Times", size=10)
        self.set_left_margin(10)
        self.set_right_margin(10)
        self.multi_cell(0, 10, content)

def sanitize_text(text):
    return text.encode("latin-1", "replace").decode("latin-1")

def create_application_pdf(application_text, file_name="application.pdf"):
    pdf = ApplicationPDF(format="A4")
    pdf.add_page()
    sanitized_text = sanitize_text(application_text)
    pdf.add_body(sanitized_text)
    pdf.output(file_name)
    return file_name

def refine_prompt(prompt, refine_missing=True):
    additional_instruction = (
        "Check for missing details like recipient, purpose, sender information, or specifics of the request." if refine_missing
        else "Exclude notes about missing details and finalize the text."
    )
    response = lm(
        prompt=(
            f"Refine the following application draft to ensure it is complete and professional. {additional_instruction}\n\n"
            f"User Input: {prompt}"
        ),
        max_tokens=500
    )
    return response[0].strip() if response else "Error: No response received from the model."

def check_missing_details(prompt):
    """
    Use the dspy LM to determine if there are missing details in the provided draft.
    Returns True if missing details are identified, otherwise False.
    """
    response = lm(
        prompt=(
            f"Analyze the following application draft and determine if any essential information is missing, "
            f"such as recipient, purpose, sender details, or required specifics. Respond with 'true' if missing "
            f"details are identified and 'false' otherwise.\n\n"
            f"Draft: {prompt}"
        ),
        max_tokens=1
    )
    return response[0].strip().lower() == "true"

def refine_final_prompt(prompt):
    """
    Use the dspy LM to refine the user-provided prompt, removing missing details notes.
    """
    response = lm(
        prompt=(
            f"Refine the following application draft to ensure it is complete and professional. "
            f"Exclude notes about missing details or incomplete information in the final draft."
            f"Exclude any text that is present between [] including open '[' and ']'."
            f"output shoud reduce the space between lines and space between paragraphs."
            f"remove date line which is coming after subject line"
            f"Applicant information should come in first paragraph in body section after sir/madam"
            f"User Input: {prompt}"
        ),
        max_tokens=500
    )
    print("final refined response:\n")
    print(response)
    return response[0].strip() if response else "Error: No response received from the model."
# Callback function to handle radio button change
def handle_action_change():
    global action
    action = st.session_state.action
    st.session_state.changed = True

def reset_session():
    for key in list(st.session_state.keys()):
        del st.session_state[key]

# Streamlit app
st.title("Application Generator")

if st.button("New Application"):
    reset_session()
    st.session_state.user_prompt=""
    st.experimental_rerun()

# Step 1: Initial Prompt
user_prompt = st.text_area("Enter your application request:", "", key="user_prompt")

if st.button("Refine and Check for Missing Details"):
    if user_prompt.strip():
        st.session_state.refined_response = refine_prompt(user_prompt)
        st.session_state.has_missing_details = check_missing_details(st.session_state.refined_response)
    else:
        st.warning("Please enter an application request.")

# Step 2: Process the refined response
if "refined_response" in st.session_state:
    refined_response = st.session_state.refined_response
    has_missing_details = st.session_state.has_missing_details

    if has_missing_details:
        st.warning("The application draft indicates missing information:")
        st.text(refined_response)

        # Step 3: Radio button with on_change callback
        st.radio(
            "What would you like to do?",
            ["Select an option", "Provide Missing Details", "Continue with Missing Details"],
            index=0,
            key="action",
            on_change=handle_action_change
        )

    if "changed" in st.session_state and st.session_state.changed:
        if st.session_state.action == "Provide Missing Details":
            # Temporary text area for missing details
            missing_details = st.text_area("Enter the missing details:", key="missing_details")
            if st.button("Refine with Missing Details"):
                # Combine user_prompt with missing details
                updated_prompt = f"{st.session_state.user_prompt}\n{missing_details}"
                print(updated_prompt)
                # Store updated prompt in a separate variable before rerun
                st.session_state["updated_prompt"] = updated_prompt
                
                # Refine the updated prompt
                st.session_state.refined_response = refine_prompt(updated_prompt, refine_missing=False)
                st.session_state.changed = False
                
                # Use experimental rerun to refresh state
                st.experimental_rerun()

                # Outside the conditional logic, update user_prompt with the new refined prompt if available
                if "updated_prompt" in st.session_state:
                    st.session_state.user_prompt = st.session_state.pop("updated_prompt")



        elif st.session_state.action == "Continue with Missing Details":
            # Proceed with the current refined response
            st.session_state.refined_response = refine_prompt(refined_response, refine_missing=False)
            st.session_state.changed = False
        

    # Step 4: Generate PDF
    if "refined_response" in st.session_state and st.button("Generate PDF"):
        final_response = refine_final_prompt(st.session_state.refined_response)
        file_path = create_application_pdf(final_response)
        st.success(f"PDF generated: {file_path}")
        st.download_button("Download PDF", open(file_path, "rb"), file_name="application.pdf")
else:
    st.info("Refine the application draft to proceed.")
