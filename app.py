import tkinter as tk
import subprocess

# ----------------- DNS Functions -----------------
def set_custom_dns():
    try:
        # Replace "Wi-Fi" with your network adapter name
        subprocess.run('netsh interface ip set dns name="Wi-Fi" static 8.8.8.8', shell=True)
        status_label.config(text="Custom DNS ON (8.8.8.8)")
    except Exception as e:
        status_label.config(text=f"Error: {e}")

def set_auto_dns():
    try:
        subprocess.run('netsh interface ip set dns name="Wi-Fi" dhcp', shell=True)
        status_label.config(text="Automatic DNS ON")
    except Exception as e:
        status_label.config(text=f"Error: {e}")

def toggle_dns():
    if dns_var.get() == 1:
        set_custom_dns()
    else:
        set_auto_dns()

# ----------------- Home Screen -----------------
def open_home():
    login_window.destroy()  # close login window

    global home_window, dns_var, status_label
    home_window = tk.Tk()
    home_window.title("Home Screen")
    home_window.geometry("400x200")

    tk.Label(home_window, text="DNS Connection Control", font=("Arial", 14)).pack(pady=20)

    dns_var = tk.IntVar()
    toggle_button = tk.Checkbutton(home_window, text="Custom DNS", variable=dns_var, command=toggle_dns)
    toggle_button.pack()

    status_label = tk.Label(home_window, text="Automatic DNS ON")
    status_label.pack(pady=20)

    home_window.mainloop()

# ----------------- Login Screen -----------------
login_window = tk.Tk()
login_window.title("Login")
login_window.geometry("300x200")

tk.Label(login_window, text="Username").pack(pady=(20,0))
username_entry = tk.Entry(login_window)
username_entry.pack()

tk.Label(login_window, text="Password").pack(pady=(10,0))
password_entry = tk.Entry(login_window, show="*")
password_entry.pack()

login_button = tk.Button(login_window, text="Login", command=open_home)
login_button.pack(pady=20)

login_window.mainloop()
