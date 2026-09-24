-- База на сервіс. Блок не має доступу до чужих таблиць — це головна межа
-- всієї архітектури, і тримається вона саме тут.
CREATE DATABASE customers OWNER baymeister;
CREATE DATABASE identity  OWNER baymeister;
CREATE DATABASE vehicles  OWNER baymeister;

-- Далі, у міру появи блоків:
-- CREATE DATABASE catalog    OWNER baymeister;
