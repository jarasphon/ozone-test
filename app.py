import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
import math
import io
import base64
import datetime
from fpdf import FPDF

# --- Page Configuration ---
st.set_page_config(
    page_title="Ozone Dynamics Explorer",
    page_icon="💨",
    layout="wide"
)

# --- Core Simulation Logic ---
def estimate_k(temp_c, ph, wq_factor):
    base_k = 0.005
    temp_factor = max(0.1, math.pow(2, (temp_c - 20) / 10))
    ph_factor = 1.0 + max(0, (ph - 7) * 0.25) if ph > 7 else 1.0 - (7 - ph) * 0.1
    ph_factor = max(0.1, ph_factor)
    wq_factor = max(0.1, wq_factor)
    return base_k * temp_factor * ph_factor * wq_factor

def simulate_ozone(t_array, ozone_gph, volume_l, k, fill_hr):
    R = (ozone_gph * 1000) / (volume_l * 60)
    t_fill_end = fill_hr * 60
    c_peak = (R / k) * (1 - math.exp(-k * t_fill_end)) if k > 0 else R * t_fill_end
    conc = []
    for t_min in t_array:
        current_conc = 0
        if t_min <= t_fill_end:
            current_conc = (R / k) * (1 - math.exp(-k * t_min)) if k > 0 else R * t_min
        else:
            time_after_fill = t_min - t_fill_end
            current_conc = c_peak * math.exp(-k * time_after_fill) if k > 0 else c_peak
        conc.append(max(0, current_conc))
    return np.array(conc)

# --- State Management ---
def create_default_scenario(index):
    defaults = [(5.0, 1.0, 200.0, 25.0, 7.0, 1.0, 6.0), (10.0, 0.5, 200.0, 30.0, 8.0, 1.5, 6.0)]
    d = defaults[index % len(defaults)]
    return {"name": f"Scenario {index + 1}", "ozone_rate": d[0], "fill_hr": d[1], "volume": d[2], "temp": d[3], "ph": d[4], "wq": d[5], "sim_hr": d[6]}

if 'scenarios' not in st.session_state:
    st.session_state.scenarios = [create_default_scenario(0)]

def add_scenario():
    st.session_state.scenarios.append(create_default_scenario(len(st.session_state.scenarios)))

def remove_scenario(index):
    if len(st.session_state.scenarios) > 1:
        st.session_state.scenarios.pop(index)
    else:
        st.toast("Cannot remove the last scenario.", icon="⚠️")

# --- Report Generation ---
class PDF(FPDF):
    def header(self):
        try:
            self.add_font('THSarabunNew', '', 'THSarabunNew.ttf', uni=True)
            self.set_font('THSarabunNew', '', 16)
        except RuntimeError:
            self.set_font('Arial', 'B', 16) # Fallback font
        self.cell(0, 10, 'Ozone Dynamics Simulation Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        try:
            self.set_font('THSarabunNew', '', 8)
        except RuntimeError:
            self.set_font('Arial', 'I', 8) # Fallback font
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf_report(fig, table_df):
    pdf = PDF()
    pdf.add_page()
    
    with io.BytesIO() as img_buffer:
        fig.savefig(img_buffer, format="png", dpi=300, bbox_inches='tight')
        pdf.image(img_buffer, x=10, y=30, w=190)

    pdf.ln(105) 
    
    try:
        pdf.set_font('THSarabunNew', '', 12)
    except RuntimeError:
        pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, 'Scenario Summary', 0, 1, 'L')
    
    try:
        pdf.set_font('THSarabunNew', '', 9)
    except RuntimeError:
        pdf.set_font('Arial', '', 9)
        
    col_widths = [25, 20, 15, 15, 15, 10, 15, 20, 20]
    for i, header in enumerate(table_df.columns):
        pdf.cell(col_widths[i], 8, header, 1, 0, 'C')
    pdf.ln()

    for _, row in table_df.iterrows():
        for i, item in enumerate(row):
            pdf.cell(col_widths[i], 6, str(item), 1, 0, 'C')
        pdf.ln()
        
    return pdf.output(dest='S').decode('latin-1') # <<< บรรทัดที่แก้ไข

def generate_html_report(fig, table_df):
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format="png", bbox_inches='tight')
    img_str = base64.b64encode(img_buffer.getvalue()).decode()
    
    table_html = table_df.to_html(index=False, justify='center', border=1).replace('<table', '<table style="width:100%; border-collapse: collapse; border: 1px solid #ccc;"').replace('<th>', '<th style="background-color: #f2f2f2; padding: 8px; border: 1px solid #ccc;">').replace('<td>', '<td style="padding: 8px; border: 1px solid #ccc; text-align: center;">')

    html = f"""
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Ozone Report</title><style>body {{ font-family: sans-serif; margin: 2em; }} .container {{ max-width: 1000px; margin: auto; }} h1, h2 {{ color: #2c3e50; }} img {{ max-width: 100%; border: 1px solid #ddd; padding: 5px; }} .section {{ margin-top: 2em; }}</style></head><body><div class="container"><h1>Ozone Dynamics Simulation Report</h1><p>Generated on: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p><div class="section"><h2>Concentration Over Time</h2><img src="data:image/png;base64,{img_str}" alt="Ozone Graph"></div><div class="section"><h2>Scenario Summary</h2>{table_html}</div></div></body></html>
    """
    return html

# --- Main App UI ---
st.title("💨 Ozone Dynamics Explorer")
st.markdown("จำลองความเข้มข้นของโอโซนในน้ำตามเวลา พร้อมเปรียบเทียบปัจจัยต่างๆ")

with st.sidebar:
    st.header("⚙️ ควบคุม Scenario")
    st.button("➕ Add Scenario", on_click=add_scenario, use_container_width=True)
    st.markdown("---")
    for i, s in enumerate(st.session_state.scenarios):
        with st.expander(f"**{s['name']}**", expanded=True):
            s['ozone_rate'] = st.number_input("Ozone Rate (g/h)", value=s['ozone_rate'], key=f"ozone_{i}", min_value=0.1)
            s['fill_hr'] = st.number_input("Fill Duration (hr)", value=s['fill_hr'], key=f"fill_{i}", min_value=0.1)
            s['volume'] = st.number_input("Water Volume (L)", value=s['volume'], key=f"vol_{i}", min_value=1.0)
            s['temp'] = st.number_input("Temperature (°C)", value=s['temp'], key=f"temp_{i}")
            s['ph'] = st.number_input("pH", value=s['ph'], key=f"ph_{i}", min_value=0.0, max_value=14.0, step=0.1)
            s['wq'] = st.number_input("Water Quality Factor", value=s['wq'], key=f"wq_{i}", min_value=0.1, help="1=Pure, >1=Impurities")
            s['sim_hr'] = st.number_input("Simulation Duration (hr)", value=s['sim_hr'], key=f"sim_{i}", min_value=0.1)
            st.button("➖ Remove", on_click=remove_scenario, args=(i,), key=f"remove_{i}", use_container_width=True)

# --- Process Data and Display Outputs ---
chart_data_list = []
table_data_list = []

for s in st.session_state.scenarios:
    k = estimate_k(s['temp'], s['ph'], s['wq'])
    t_values = np.linspace(0, s['sim_hr'] * 60, 500)
    c_values = simulate_ozone(t_values, s['ozone_rate'], s['volume'], k, s['fill_hr'])
    table_data_list.append({"Scenario": s['name'], "Ozone Rate (g/h)": s['ozone_rate'], "Fill (hr)": s['fill_hr'], "Volume (L)": s['volume'], "Temp (°C)": s['temp'], "pH": s['ph'], "Water QF": s['wq'], "k (/min)": f"{k:.4f}", "T½ (min)": round(math.log(2) / k, 2) if k > 0 else "inf"})
    chart_data_list.append(pd.DataFrame({s['name']: c_values}, index=pd.Series(t_values, name="Time (min)")))

if chart_data_list:
    combined_chart_df = pd.concat(chart_data_list, axis=1)
    st.line_chart(combined_chart_df)

if table_data_list:
    summary_df = pd.DataFrame(table_data_list)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("⬇️ ส่งออกรายงาน (Export Report)")
    
    fig, ax = plt.subplots(figsize=(10, 6))
    for col in combined_chart_df.columns:
        ax.plot(combined_chart_df.index, combined_chart_df[col], label=col)
    ax.set_title("Ozone Concentration Over Time")
    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Ozone Concentration (mg/L)")
    ax.grid(True)
    ax.legend()
    
    html_content = generate_html_report(fig, summary_df)
    pdf_content = generate_pdf_report(fig, summary_df)
    plt.close(fig)

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(label="📄 Export to HTML", data=html_content, file_name="ozone_report.html", mime="text/html", use_container_width=True)
    with col2:
        st.download_button(label="📕 Export to PDF", data=pdf_content, file_name="ozone_report.pdf", mime="application/pdf", use_container_width=True)

with st.expander("📖 ทฤษฎีและการคำนวณ (Ozone Decay Theory)"):
    st.markdown("""
    โอโซน (O₃) ในน้ำจะเกิดกระบวนการเติม (Injection) และการสลายตัว (Decay) ไปพร้อมๆ กัน

    **1. ช่วงเติมโอโซน (พร้อมการสลายตัว)**
    - การเปลี่ยนแปลงความเข้มข้น: `dC/dt = R - kC`
    - ความเข้มข้น ณ เวลา t: **`C(t) = (R/k) * (1 - e^(-kt))`**

    **2. ช่วงสลายตัว (หลังหยุดเติม)**
    - การเปลี่ยนแปลงความเข้มข้น: `dC/dt = -kC`
    - ความเข้มข้น ณ เวลา t: **`C(t) = C_peak * e^(-k * (t - t_fill_end))`**

    **ตัวแปร:**
    - **C(t)**: ความเข้มข้นของโอโซน (mg/L)
    - **R**: อัตราการเพิ่มของโอโซนในระบบ (mg/L/min)
    - **k**: ค่าคงที่การสลายตัวอันดับหนึ่ง (min⁻¹)
    - **t**: เวลา (นาที)
    - **C_peak**: ความเข้มข้นสูงสุด ณ เวลาที่หยุดเติมโอโซน

    **ค่าครึ่งชีวิต (Half-Life, T½):**
    - คือเวลาที่โอโซนใช้ในการสลายตัวจนเหลือครึ่งหนึ่งของความเข้มข้นเริ่มต้น
    - **`T½ = ln(2) / k`** (โดย ln(2) ≈ 0.693)
    """)