Project Plan
You can save this directly as project_plan.md to guide the entire lifecycle of your analysis.
Subject to changes, last change at: 11:50am 11.05.2026

1. Phase 1: Project Setup & Documentation
1.1. Initialize Repository: Create the project folder structure (e.g., /data, /docs, /scripts, /ui).
1.2. Document Constants: Save the tax and duty parameters as taxes_and_duties_history.md in the /docs folder.
1.3. Define Scope: Finalize this project plan and place it in the root directory.
2. Phase 2: Data Collection & Validation
2.1. Fuel Station Prices (Intraday Data):
Download historical CSV dumps from Tankerkönig / MTS-K.
Target scope: Minimum 2021 to 2026 (focusing heavily on May-Sep 2022 and May-Jun 2026).
2.2. Commodity & Benchmark Data (Daily Data):
Download ICE Dated Brent Crude Oil prices (USD/Barrel).
Download EUR/USD exchange rate historical data.
(Optional but recommended) Download Crack Spreads (Refinery margins) if available.
2.3. Data Validation & Integrity Checks:
Check for missing values (NaNs) or extreme outliers in fuel prices (e.g., stations reporting 9.99€/liter due to errors).
Ensure Timezone consistency (Fuel prices are usually in Europe/Berlin local time, while oil benchmarks might be in UTC/EST).
Verify that all required datasets overlap correctly in the timeline.
3. Phase 3: Data Processing & Internal Analysis (Scripting)
3.1. ETL Pipeline (Extract, Transform, Load):
Write a script to convert oil prices from USD/Barrel to EUR/Liter.
Merge the daily oil/currency data with the minute/hourly fuel station data using the timestamp.
3.2. Tax Deduction Script (Net Margin Calculation):
Implement the logic from the taxes_and_duties_history.md matrix.
Calculate: Gross Price -> subtract VAT -> subtract Energy Tax, CO2, EBV -> equals Net Product Price.
Calculate: Net Product Price - EUR Brent Price = Corporate Margin.
3.3. Intraday Pattern Script (The 12:00 PM Hike):
Group the data by hour and minute.
Generate internal visual plots (e.g., using Matplotlib/Seaborn) to prove the systematic price hikes at specific times (like 12:00 PM).
3.4. Excess Profit Script (The Fuel Discount Analysis):
Compare the Corporate Margin before, during, and after the 2022 and 2026 fuel discounts.
Generate internal plots to see if the margin spiked exactly when the tax dropped.
4. Phase 4: Final Visualization & Modern UI
4.1. Select UI Framework: Choose a modern, interactive framework (e.g., Python-based like Streamlit or Dash, or a JS-based frontend like Next.js with Recharts/Plotly).
4.2. Build Interactive Dashboards:
View 1 (The Discount): A timeline chart showing the gross price vs. net price vs. oil price, with highlighted background areas for the discount periods.
View 2 (The Daily Rhythm): An interactive heat map or line chart showing average prices by time of day, allowing the user to filter by year or month.
View 3 (The Margin): A clear, isolated chart showing the exact profit margin of the oil companies over time.
4.3. Polish & Deploy: Add tooltips explaining the taxes to the end-user, ensure mobile responsiveness, and deploy the app (e.g., via Vercel, Heroku, or Streamlit Cloud).
