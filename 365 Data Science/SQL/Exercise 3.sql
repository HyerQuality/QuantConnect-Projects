CREATE TABLE Companies
(
	Company_ID VARCHAR(255),
    Company_Name VARCHAR(255) DEFAULT "X",
    Headquarters_Phone_Number INT(12),
PRIMARY KEY (Company_ID),
UNIQUE KEY (Headquarters_Phone_Number)
);

ALTER TABLE Companies
MODIFY Headquarters_Phone_Number INT(12) NULL;

ALTER TABLE Companies
MODIFY Headquarters_Phone_Number INT(12) NOT NULL;

DROP TABLE Companies;