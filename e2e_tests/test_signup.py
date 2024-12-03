from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

driver = webdriver.Firefox()

try:
    driver.get("https://queue-management-1hca.onrender.com/")
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "login-button")))
    login_button = driver.find_element(By.ID, "login-button")
    login_button.click()
    signup_button = driver.find_element(By.ID, "signup-button")
    signup_button.click()
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "username")))
    username_input = driver.find_element(By.ID, "username")
    email_input = driver.find_element(By.ID, "email")
    password_input = driver.find_element(By.ID, "password1")
    confirm_password_input = driver.find_element(By.ID, "password2")
    username_input.send_keys("test9")
    password_input.send_keys("hackme99")
    email_input.send_keys("test9@gmail.com")
    confirm_password_input.send_keys("hackme99")
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "register-submit")))
    register_submit = driver.find_element(By.ID, "register-submit")
    register_submit.click()
    WebDriverWait(driver, 30).until(EC.url_contains("/manager/queue"))
    current_url = driver.current_url
    print("Test passed")

except Exception as e:
    print(f"Test failed: {e}")

finally:
    driver.quit()
