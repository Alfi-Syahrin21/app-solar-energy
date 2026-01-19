import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# 1. SETUP TAMPILAN
# ==========================================
st.set_page_config(page_title="Simulasi Solar & Baterai", layout="wide")

st.title("☀️ Simulator Energi: Solar Panel + Baterai")
st.markdown("---")

# ==========================================
# 2. INPUT PARAMETER (DI HALAMAN UTAMA)
# ==========================================
st.subheader("1. Konfigurasi Parameter")

# Membagi layar menjadi 3 kolom agar rapi
col_solar, col_bat, col_env = st.columns(3)

with col_solar:
    st.info("☀️ **Panel Surya**")
    SOLAR_CAPACITY_KW = st.number_input("Kapasitas (kWp)", min_value=1.0, value=5.0, step=0.5)
    TEMP_COEFF = st.number_input("Koefisien Suhu (/°C)", value=-0.004, format="%.4f")

with col_bat:
    st.warning("🔋 **Baterai**")
    BATTERY_CAPACITY_KWH = st.number_input("Kapasitas (kWh)", min_value=1.0, value=10.0, step=1.0)
    BATTERY_EFFICIENCY = st.number_input("Efisiensi Charge (%)", 80, 100, 95) / 100

with col_env:
    st.success("⚡ **Kondisi Awal**")
    BATTERY_INITIAL_SOC = st.slider("Isi Awal Baterai (%)", 0, 100, 50) / 100

st.markdown("---")

# ==========================================
# 3. UPLOAD FILE
# ==========================================
st.subheader("2. Upload Data CSV")
uploaded_file = st.file_uploader("Upload file CSV (harus ada kolom: timestamp, irradiance, suhu, beban_rumah_kw, harga_listrik)", type=["csv"])

# ==========================================
# 4. LOGIKA PROSES
# ==========================================
if uploaded_file is not None:
    # Load Data
    try:
        df = pd.read_csv(uploaded_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        st.caption(f"✅ File berhasil dimuat! Total durasi: {len(df)//288} hari ({len(df)} baris data).")
    except Exception as e:
        st.error(f"Format CSV salah: {e}")
        st.stop()

    # Tombol Eksekusi (Di tengah agar jelas)
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        run_simulation = st.button("🚀 MULAI SIMULASI", use_container_width=True, type="primary")

    if run_simulation:
        with st.spinner('Sedang menghitung aliran energi...'):
            # --- ENGINE SIMULASI ---
            solar_output_list = []
            battery_soc_list = []
            grid_import_list = []
            grid_cost_list = []

            current_battery_kwh = BATTERY_CAPACITY_KWH * BATTERY_INITIAL_SOC

            # Loop Perhitungan
            for index, row in df.iterrows():
                # A. Hitung Solar
                irr = row['irradiance']
                temp = row['suhu']
                temp_factor = 1 + (TEMP_COEFF * (temp - 25))
                solar_kw = SOLAR_CAPACITY_KW * (irr / 1000) * temp_factor
                solar_kw = max(0, solar_kw)
                solar_output_list.append(solar_kw)

                # B. Hitung Neraca
                load_kw = row['beban_rumah_kw']
                time_factor = 5/60
                
                energy_solar_kwh = solar_kw * time_factor
                energy_load_kwh = load_kw * time_factor
                net_energy_kwh = energy_solar_kwh - energy_load_kwh
                
                grid_import_kwh = 0

                # C. Logika Baterai
                if net_energy_kwh > 0: # Surplus
                    energy_to_store = net_energy_kwh * BATTERY_EFFICIENCY
                    space_available = BATTERY_CAPACITY_KWH - current_battery_kwh
                    
                    if energy_to_store <= space_available:
                        current_battery_kwh += energy_to_store
                    else:
                        current_battery_kwh = BATTERY_CAPACITY_KWH
                else: # Defisit
                    energy_needed = abs(net_energy_kwh)
                    if current_battery_kwh >= energy_needed:
                        current_battery_kwh -= energy_needed
                    else:
                        shortfall = energy_needed - current_battery_kwh
                        current_battery_kwh = 0
                        grid_import_kwh = shortfall
                
                battery_soc_list.append(current_battery_kwh)
                grid_import_list.append(grid_import_kwh)
                grid_cost_list.append(grid_import_kwh * row['harga_listrik'])
            
            # Masukkan hasil ke DataFrame
            df['solar_output_kw'] = solar_output_list
            df['battery_level_kwh'] = battery_soc_list
            df['battery_percentage'] = (df['battery_level_kwh'] / BATTERY_CAPACITY_KWH) * 100
            df['grid_import_kwh'] = grid_import_list
            df['biaya_listrik_rp'] = grid_cost_list

            # ==========================================
            # 5. OUTPUT HASIL
            # ==========================================
            st.divider()
            st.subheader("3. Hasil Analisis")

            # Metrics Ringkasan
            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric("Total Produksi Solar", f"{sum(solar_output_list)*5/60:,.2f} kWh")
            m_col2.metric("Total Beli dari PLN", f"{sum(grid_import_list):,.2f} kWh", delta_color="inverse")
            m_col3.metric("Estimasi Tagihan", f"Rp {sum(grid_cost_list):,.0f}", delta_color="inverse")

            # Grafik
            st.write("#### 📈 Grafik Performa (3 Hari Pertama)")
            subset = df.head(288 * 3) 
            
            fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 10), sharex=True)
            
            ax1.plot(subset['timestamp'], subset['solar_output_kw'], color='green', label='Solar (kW)')
            ax1.plot(subset['timestamp'], subset['beban_rumah_kw'], color='red', linestyle='--', label='Beban (kW)')
            ax1.set_ylabel("Daya (kW)")
            ax1.legend(loc="upper right")
            ax1.grid(True, alpha=0.3)
            
            ax2.fill_between(subset['timestamp'], subset['battery_percentage'], color='blue', alpha=0.1)
            ax2.plot(subset['timestamp'], subset['battery_percentage'], color='blue', label='Baterai (%)')
            ax2.set_ylabel("SoC (%)")
            ax2.set_ylim(0, 110)
            ax2.grid(True, alpha=0.3)
            
            ax3.bar(subset['timestamp'], subset['grid_import_kwh'], color='black', label='Impor PLN (kWh)', width=0.01)
            ax3.set_ylabel("Energi (kWh)")
            ax3.legend(loc="upper right")
            ax3.grid(True, alpha=0.3)
            
            st.pyplot(fig)

            # Download
            csv_result = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="💾 Download Laporan Lengkap (CSV)",
                data=csv_result,
                file_name="hasil_simulasi_final.csv",
                mime="text/csv",
                use_container_width=True
            )
else:
    st.info("👆 Silakan upload file CSV time-series dulu untuk memulai.")