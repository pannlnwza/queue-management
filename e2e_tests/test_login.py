from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

driver = webdriver.Firefox()

try:
    driver.get("http://127.0.0.1:8000/")
    login_button = driver.find_element(By.ID, "login-button")
    login_button.click()
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username")))
    username_input = driver.find_element(By.ID, "username")
    password_input = driver.find_element(By.ID, "password")
    username_input.send_keys("demo1")
    password_input.send_keys("hackme11")
    login_submit = driver.find_element(By.ID, "login-submit")
    login_submit.click()
    WebDriverWait(driver, 10).until(EC.url_contains("/manager/queue"))
    current_url = driver.current_url
    assert "/manager/queue" in current_url, f"Expected '/queue' in URL but got {current_url}"

finally:
    driver.quit()
