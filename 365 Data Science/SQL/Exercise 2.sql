CREATE TABLE Customers
(
	Customer_ID INT AUTO_INCREMENT,
    First_Name VARCHAR(255),
    Last_Name VARCHAR(255),
    Email_Address VARCHAR(255),
    Number_Of_Complaints INT,
PRIMARY KEY (Customer_ID)
);

ALTER TABLE Customers
ADD COLUMN Gender ENUM('M','F') AFTER Last_Name;

INSERT INTO Customers(First_Name, Last_Name, Gender, Email_Address, Number_Of_Complaints)
Values ('John', 'Macklnley', 'M', 'john.mcklnley@365careers.com', 0);