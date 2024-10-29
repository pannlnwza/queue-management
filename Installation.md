# Installation Instructions for Queue Management

1. Clone the repository
   ```
   https://github.com/pannlnwza/queue-management.git
   ```
2. Change the directory into the repo
   ```
   cd queue-management
   ```

3. Activate the virtual environment using one of the following commands, depending on your operating system

    ```shell
    python -m venv env
    ```
    
    - **Windows**
    
      ```shell
      env\Scripts\activate
      ```
    
    - **macOS/Linux**
    
        ```shell
        source env/bin/activate
        ```

4. Install the required packages using pip
   ```shell
   pip install -r requirements.txt
   ```
   
5. Create the .env file by copying the contents of sample.env
   - **macOS/Linux**
     ```shell
     cp sample.env .env
     ```
   - **Windows**
     ```shell
     copy sample.env .env
     ```
     You can edit the .env file to set any environment-specific values as needed.


6. Run migrations
   ```shell
   python manage.py makemigrations
   python manage.py migrate
   ```

7. Run tests
   ```shell
   python manage.py test
   ```
   
8. Start the Django server
   ```shell
   python manage.py runserver
   ```
