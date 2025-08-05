import pandas as pd

pd.set_option('display.max_columns', None)   # show every column
pd.set_option('display.expand_frame_repr', False)  # stop line-wrapping
pd.set_option('display.max_colwidth', None)  # don’t truncate long text

file_path = 'loveMeDataUpdated.xlsx'
sheet     = 'Sheet1'              # adjust if your sheet is named differently

df = pd.read_excel(file_path, sheet_name=sheet)

#read_excel is a vectorized bulk loader, calls openpyxl and reads everything in the file and prints
# it in a ready dataframe


mask = df["SKU"].isna()
df.loc[mask, "SKU"] = (
    "SKU-" + (mask.cumsum()).astype(str).str.zfill(4)   # SKU-0001, SKU-0002…
)

# save back
with pd.ExcelWriter("loveMeDataUpdated.xlsx", engine="openpyxl",
                    mode="a", if_sheet_exists="replace") as xl:
    df.to_excel(xl, sheet_name="Products", index=False)


