from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
import time

def login(driver, base_url):
    driver.get(base_url)
    time.sleep(1)
    login_button = driver.find_element(By.ID, "login-button")
    login_button.click()
    time.sleep(1)
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.ID, "username"))
    )
    username_input = driver.find_element(By.ID, "username")
    password_input = driver.find_element(By.ID, "password")
    username_input.send_keys("demo1")
    time.sleep(1)
    password_input.send_keys("hackme11")
    time.sleep(1)
    login_submit = driver.find_element(By.ID, "login-submit")
    login_submit.click()
    time.sleep(1)
    WebDriverWait(driver, 30).until(EC.url_contains("/manager/queue"))


def test_create_queue():
    driver = webdriver.Firefox()
    base_url = "https://queue-management-1hca.onrender.com/"

    try:
        login(driver, base_url)
        time.sleep(1)
        create_queue_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "create-queue-button"))
        )
        create_queue_button.click()
        time.sleep(1)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "queue-name"))
        )

        queue_name_input = driver.find_element(By.ID, "queue-name")
        queue_name_input.send_keys("Test Queue")
        time.sleep(1)
        queue_description_input = driver.find_element(By.ID,"queue-description")
        queue_description_input.send_keys("This is a test queue.")
        time.sleep(1)
        category_select = driver.find_element(By.ID, "category")
        select = Select(category_select)
        select.select_by_visible_text("Restaurant")
        time.sleep(1)
        next_button = driver.find_element(By.ID, "nextBtn")
        next_button.click()
        time.sleep(1)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "latitudeInput"))
        )

        latitude_input = driver.find_element(By.ID, "latitudeInput")
        longitude_input = driver.find_element(By.ID, "longitudeInput")
        latitude_input.send_keys("13.848259")
        time.sleep(1)
        longitude_input.send_keys("100.567543")
        time.sleep(1)
        search_button = driver.find_element(By.ID, "searchByLatLonBtn")
        search_button.click()
        time.sleep(2)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "map"))
        )
        next_button = driver.find_element(By.ID, "nextBtn")
        next_button.click()
        time.sleep(1)
        next_button = driver.find_element(By.ID, "nextBtn")
        next_button.click()
        time.sleep(1)
        WebDriverWait(driver, 30).until(EC.url_contains("/manager/queue"))
        current_url = driver.current_url
        assert "/manager/queue" in current_url, f"Expected '/manager/queue' in URL but got {current_url}"
        success_message = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH,
                                            "//div[@id='toast-container']//div[contains(@class, 'alert-success')]//span"))
        )
        assert "Queue 'Test Queue' created successfully" in success_message.text, \
            f"Expected success message but got: {success_message.text}"
        print("Test passed")

    except Exception as e:
        print(f"Test failed: {e}")

    finally:
        driver.quit()


test_create_queue()
