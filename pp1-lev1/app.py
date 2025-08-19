from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import os
import matplotlib
matplotlib.use('Agg')  # Add this before importing pyplot!
import matplotlib.pyplot as plt

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
STATIC_FOLDER = 'static'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def save_plot(fig, filename, plot_subfolder):
    static_subdir = os.path.join(STATIC_FOLDER, plot_subfolder)
    os.makedirs(static_subdir, exist_ok=True)
    plot_path = os.path.join(static_subdir, filename)
    fig.savefig(plot_path, bbox_inches='tight')
    plt.close(fig)
    return f"{plot_subfolder}/{filename}"

def find_column(cols, keywords):
    for col in cols:
        for key in keywords:
            if key in col.lower():
                return col
    return None

def choose_categorical_for_pie(df, cat_cols):
    pie_cols = []
    for col in cat_cols:
        nunique = df[col].nunique()
        if 2 <= nunique <= 6:
            pie_cols.append(col)
    return pie_cols

def choose_pairs_for_scatter(df, num_cols):
    if len(num_cols) >= 2:
        return [(num_cols[0], num_cols[1])]
    return []

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        csv = request.files['file']
        path = os.path.join(app.config['UPLOAD_FOLDER'], csv.filename)
        csv.save(path)
        return redirect(url_for('eda', filename=csv.filename))
    return render_template('index.html')

@app.route('/eda/<filename>')
def eda(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df = pd.read_csv(path)

    csv_base = os.path.splitext(filename)[0]
    plot_subfolder = csv_base

    preview = df.head(10).to_html(classes="table table-striped", index=False)
    columns = list(df.columns)
    dtypes = df.dtypes.astype(str).to_dict()
    missing = df.isna().sum().to_dict()
    num_cols = df.select_dtypes(include='number').columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

    num_stats = df[num_cols].describe().T.round(2) if num_cols else None
    cat_stats = {col: df[col].value_counts().head().to_dict() for col in cat_cols}
    plots = []

    for col in num_cols:
        fig, ax = plt.subplots()
        df[col].hist(ax=ax, bins=10, color='steelblue')
        ax.set_title(f'Histogram of {col}')
        ax.set_xlabel(col)
        path_hist = save_plot(fig, f'hist_{col}.png', plot_subfolder)
        plots.append((f'Histogram: {col}', path_hist))

    pie_cols = choose_categorical_for_pie(df, cat_cols)
    bar_cols = [col for col in cat_cols if col not in pie_cols]
    for col in pie_cols:
        fig, ax = plt.subplots()
        df[col].value_counts().plot.pie(ax=ax, autopct='%.1f%%')
        ax.set_ylabel('')
        ax.set_title(f'Pie Chart: {col}')
        path_pie = save_plot(fig, f'pie_{col}.png', plot_subfolder)
        plots.append((f'Pie Chart: {col}', path_pie))
    for col in bar_cols:
        fig, ax = plt.subplots()
        df[col].value_counts().head(10).plot(kind='bar', ax=ax, color='lightgreen')
        ax.set_title(f'Top 10 Values: {col}')
        path_bar = save_plot(fig, f'bar_{col}.png', plot_subfolder)
        plots.append((f'Bar Chart: {col}', path_bar))

    date_col = None
    for col in columns:
        if 'date' in col.lower() or 'time' in col.lower():
            try:
                df[col] = pd.to_datetime(df[col])
                date_col = col
                break
            except:
                continue
    if date_col and num_cols:
        df['year_month'] = df[date_col].dt.to_period('M')
        trend = df.groupby('year_month')[num_cols[0]].sum()
        fig, ax = plt.subplots()
        trend.plot(ax=ax, marker='o')
        ax.set_title(f"{num_cols} by Month")
        ax.set_ylabel(num_cols)
        ax.set_xlabel("Month")
        path_trend = save_plot(fig, f'trend.png', plot_subfolder)
        plots.append((f'Time Series: {num_cols} by Month', path_trend))

    scatter_pairs = choose_pairs_for_scatter(df, num_cols)
    for xcol, ycol in scatter_pairs:
        fig, ax = plt.subplots()
        ax.scatter(df[xcol], df[ycol], alpha=0.6)
        ax.set_xlabel(xcol)
        ax.set_ylabel(ycol)
        ax.set_title(f"Scatter Plot: {xcol} vs {ycol}")
        path_scat = save_plot(fig, f'scatter_{xcol}_vs_{ycol}.png', plot_subfolder)
        plots.append((f"Scatter: {xcol} vs {ycol}", path_scat))

    if num_cols and cat_cols:
        for cat in cat_cols[:1]:
            for num in num_cols[:1]:
                fig, ax = plt.subplots(figsize=(8, 4))
                top_categories = df[cat].value_counts().head(6).index
                df_box = df[df[cat].isin(top_categories)]
                df_box.boxplot(column=num, by=cat, ax=ax)
                plt.title(f"Boxplot of {num} by {cat}")
                plt.suptitle('')
                plt.xlabel(cat)
                plt.ylabel(num)
                path_box = save_plot(fig, f'box_{num}_by_{cat}.png', plot_subfolder)
                plots.append((f"Boxplot: {num} by {cat}", path_box))

    customer_keys = ['customer', 'user', 'buyer', 'client']
    product_keys = ['product', 'item', 'category', 'sku']
    cust_col = find_column(columns, customer_keys)
    prod_col = find_column(columns, product_keys)
    amt_candidates = [c for c in columns if any(k in c.lower() for k in ['amount', 'sales', 'revenue', 'total'])]
    amt_col = amt_candidates[0] if amt_candidates else None

    cust_analysis_html = ""
    if cust_col:
        top_customers = df[cust_col].value_counts().head(10)
        cust_analysis_html += "<b>Top 10 Customers (by Frequency):</b><br>" + top_customers.to_frame().to_html(header=["Purchase Count"], classes="table", index=True)
        if amt_col and amt_col in df.columns:
            try:
                top_spenders = df.groupby(cust_col)[amt_col].sum().sort_values(ascending=False).head(10)
                cust_analysis_html += "<br><b>Top 10 Customers by Total Amount:</b><br>" + top_spenders.to_frame().to_html(header=["Total Amount"], classes="table", index=True)
            except Exception:
                pass
    else:
        cust_analysis_html = "<i>No customer column detected.</i>"

    prod_analysis_html = ""
    if prod_col:
        top_products = df[prod_col].value_counts().head(10)
        prod_analysis_html += "<b>Top 10 Products/Categories (by Frequency):</b><br>" + top_products.to_frame().to_html(header=["Count"], classes="table", index=True)
        if amt_col and amt_col in df.columns:
            try:
                top_sellers = df.groupby(prod_col)[amt_col].sum().sort_values(ascending=False).head(10)
                prod_analysis_html += "<br><b>Top 10 Products/Categories by Total Amount:</b><br>" + top_sellers.to_frame().to_html(header=["Total Amount"], classes="table", index=True)
            except Exception:
                pass
    else:
        prod_analysis_html = "<i>No product/category column detected.</i>"

    recommendations = []
    if num_stats is not None:
        recommendations.append("Review histograms to identify skewed or outlier-prone numeric columns.")
        recommendations.append("Investigate columns with high missing value counts.")
    if len(cat_cols) > 0:
        recommendations.append("Look for dominant categories and consider grouping infrequent labels as 'Other'.")
    if date_col:
        recommendations.append("Check trends over time for any time-related columns.")
    if cust_col:
        recommendations.append("Identify top customers for targeted marketing or loyalty programs.")
    if prod_col:
        recommendations.append("Promote or bundle best-selling products/categories.")
    if scatter_pairs:
        recommendations.append("Explore numeric relationships using scatter plots.")
    if num_cols and cat_cols:
        recommendations.append("Analyze numeric distribution by groups (boxplots).")

    return render_template('eda.html',
                           preview=preview,
                           columns=columns,
                           dtypes=dtypes,
                           missing=missing,
                           num_stats=num_stats,
                           cat_stats=cat_stats,
                           plots=plots,
                           cust_analysis_html=cust_analysis_html,
                           prod_analysis_html=prod_analysis_html,
                           recommendations=recommendations)

if __name__ == '__main__':
    import socket

    port = int(os.environ.get("PORT", 0))
    if port == 0:
        # Find a free port manually
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        port = s.getsockname()[1]
        s.close()

    print(f"✅ Running Flask on dynamic port: {port}")
    app.run(host="0.0.0.0", port=port, debug=True)
