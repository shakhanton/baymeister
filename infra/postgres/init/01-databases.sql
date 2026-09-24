-- База на сервіс. Блок не має доступу до чужих таблиць — це головна межа
-- всієї архітектури, і тримається вона саме тут.
CREATE DATABASE customers OWNER baymeister;
CREATE DATABASE identity  OWNER baymeister;
CREATE DATABASE vehicles  OWNER baymeister;
CREATE DATABASE catalog   OWNER baymeister;
CREATE DATABASE scheduling OWNER baymeister;
CREATE DATABASE work_orders OWNER baymeister;
CREATE DATABASE inventory OWNER baymeister;

-- Далі, у міру появи блоків Фази 2:
-- CREATE DATABASE procurement OWNER baymeister;
