from calcelyx_app.app import App


app = App()
app.update()
assert app.title().startswith("Calcelyx")
assert app.winfo_width() >= 1000, (app.winfo_width(), app.winfo_height())
app.destroy()
print("GUI smoke test: OK")

