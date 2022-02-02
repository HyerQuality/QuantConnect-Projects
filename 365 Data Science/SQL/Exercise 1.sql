
CREATE TABLE Customers
(
	Customer_ID INT,
    First_Name VARCHAR(255),
    Last_Name VARCHAR(255),
    Email_Address VARCHAR(255),
    Number_Of_Complaints INT DEFAULT 0,
PRIMARY KEY (Customer_ID),
UNIQUE KEY (Email_Address)
);

ALTER TABLE Customers
DROP INDEX Email_Address;

CREATE TABLE Companies
(
	Company_ID VARCHAR(255),
    Company_Name VARCHAR(255) DEFAULT "X" NOT NULL,
    Headquarters_Phone_Number INT(12),
PRIMARY KEY (Company_ID),
UNIQUE KEY (Headquarters_Phone_Number)
);

CREATE TABLE Items
(
	Item_ID VARCHAR(255),
    Item VARCHAR(255),
    Unit_Price NUMERIC(10,2),
    Company_ID VARCHAR(255),
PRIMARY KEY(Item_ID)
);

ALTER TABLE Items
ADD FOREIGN KEY(Company_ID) REFERENCES Companies(Company_ID) ON DELETE CASCADE;

ALTER TABLE Items
DROP FOREIGN KEY constraint_1;

