1. Open a terminal then run:
`docker compose up`

2. Open a new terminal then run `cd init-db`
4. and `docker exec -i suitecrm_setup-mariadb-1 mysql -u bn_suitecrm -pbitnami123 < demo_data.sql`
5. app available at localhost:8080
