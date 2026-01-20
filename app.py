import tkinter as tk

# Create main window
root = tk.Tk()
root.title("My First App")
root.geometry("300x200")  # width x height

# Add a label
label = tk.Label(root, text="Hello, Windows!")
label.pack(pady=20)

# Add a button
def on_click():
    label.config(text="Button clicked!")

button = tk.Button(root, text="Click Me", command=on_click)
button.pack(pady=10)

# Run the app
root.mainloop()
