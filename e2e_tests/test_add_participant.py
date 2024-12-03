from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
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


def safe_wait(driver, by, value, timeout=30):
    for _ in range(3):
        try:
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, value)))
        except TimeoutException:
            print(f"Element not found with {by} = {value}, retrying...")
    raise TimeoutException(
        f"Element with {by} = {value} not found after retries.")


def test_create_queue_and_add_participant():
    driver = webdriver.Firefox()
    base_url = "http://127.0.0.1:8000/"
    try:
        login(driver, base_url)
        time.sleep(1)
        create_queue_button = safe_wait(driver, By.ID, "create-queue-button")
        create_queue_button.click()
        time.sleep(1)
        queue_name_input = safe_wait(driver, By.ID, "queue-name")
        queue_name_input.send_keys("Test Queue General")
        time.sleep(1)
        queue_description_input = driver.find_element(By.ID,
                                                      "queue-description")
        queue_description_input.send_keys("This is a test queue.")
        time.sleep(1)
        category_select = driver.find_element(By.ID, "category")
        select = Select(category_select)
        select.select_by_visible_text("General")
        time.sleep(1)
        next_button = driver.find_element(By.ID, "nextBtn")
        next_button.click()
        time.sleep(1)
        latitude_input = safe_wait(driver, By.ID, "latitudeInput")
        longitude_input = driver.find_element(By.ID, "longitudeInput")
        latitude_input.send_keys("13.848259")
        time.sleep(1)
        longitude_input.send_keys("100.567543")
        time.sleep(1)
        search_button = driver.find_element(By.ID, "searchByLatLonBtn")
        search_button.click()
        time.sleep(2)
        safe_wait(driver, By.ID, "map")
        next_button = driver.find_element(By.ID, "nextBtn")
        next_button.click()
        time.sleep(1)
        next_button = driver.find_element(By.ID, "nextBtn")
        next_button.click()
        time.sleep(1)
        WebDriverWait(driver, 60).until(EC.url_contains("/manager/queue"))
        row = driver.find_element(By.ID, "test queue general")
        row.click()
        time.sleep(1)
        participant_list_button = driver.find_element(By.ID,
                                                      "participant-list")
        participant_list_button.click()
        time.sleep(1)
        add_participant_button = driver.find_element(By.ID, "add-participant")
        add_participant_button.click()
        time.sleep(1)
        name = driver.find_element(By.ID, "add_name")
        phone = driver.find_element(By.ID, "add_phone")
        note = driver.find_element(By.ID, "add_notes")
        name.send_keys("Panny")
        time.sleep(1)
        phone.send_keys("0874567362")
        time.sleep(1)
        note.send_keys("For test")
        time.sleep(1)
        add_button = driver.find_element(By.ID, "submit-add")
        add_button.click()
        time.sleep(1)
        success_message = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH,
                                            "//div[@id='toast-container']//div[contains(@class, 'alert-success')]//span"))
        )
        assert "Participant has been added." in success_message.text, \
            f"Expected success message but got: {success_message.text}"
        print("Test passed")

    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        driver.quit()


test_create_queue_and_add_participant()
