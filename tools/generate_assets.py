from pathlib import Path

from calcelyx_app.pricelist import create_template_xlsx


ROOT = Path(__file__).resolve().parents[1]
create_template_xlsx(ROOT / "data" / "Cennik_przykladowy_DO_EDYCJI.xlsx")
print("Generated editable sample pricelist.")

