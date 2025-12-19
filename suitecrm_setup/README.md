# SuiteCRM Setup Guide

## Prerequisites

- **Docker**: Required to run the application containers
  - [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac)
  - [Rancher Desktop](https://rancherdesktop.io/) (Open-source alternative for Windows/Mac/Linux)
  - [Podman Desktop](https://podman-desktop.io/) (Another alternative for Windows/Mac/Linux)

## Installation Steps

1. **Install Docker**
   - Follow the installation guide for your preferred Docker solution from the links above
   - Ensure Docker service is running before proceeding

2. **Start the Application**
   - Open a terminal in the project directory
   - Run the following command:
     ```
     docker compose up
     ```

3. **Load Demo Data**
   - Open a new terminal
   - Navigate to the init-db directory:
     ```
     cd init-db
     ```
   - Import the demo data into the database:
     ```
     docker exec -i suitecrm_setup-mariadb-1 mysql -u bn_suitecrm -pbitnami123 < demo_data.sql
     ```
     > Ignore the message: `mysql: Deprecated program name. It will be removed in a future release,`

4. **Access the Application**
   - Open your browser and navigate to: http://localhost:8080/public.
   - Login with `user` as username and `bitnami` as password.
   - Browser accounts and contacts tabs to verify it's not empty.

## Troubleshooting

- If you encounter permission issues with Docker, you may need to run commands with `sudo` on Linux
- Ensure all required ports (especially 8080) are not in use by other applications
- Check Docker logs for errors: `docker compose logs`