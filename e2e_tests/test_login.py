from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

driver = webdriver.Firefox()

try:
    driver.get("https://queue-management-1hca.onrender.com/")
    time.sleep(1)
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "login-button")))
    login_button = driver.find_element(By.ID, "login-button")
    login_button.click()
    time.sleep(1)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "username")))
    username_input = driver.find_element(By.ID, "username")
    password_input = driver.find_element(By.ID, "password")
    username_input.send_keys("demo1")
    time.sleep(1)
    password_input.send_keys("hackme11")
    time.sleep(1)
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "login-submit")))
    login_submit = driver.find_element(By.ID, "login-submit")
    login_submit.click()
    time.sleep(1)
    WebDriverWait(driver, 30).until(EC.url_contains("/manager/queue"))
    current_url = driver.current_url
    assert "/manager/queue" in current_url, f"Expected '/manager/queue' in URL but got {current_url}"
    print("Test passed")

except Exception as e:
    print(f"Test failed: {e}")

finally:
    driver.quit()
