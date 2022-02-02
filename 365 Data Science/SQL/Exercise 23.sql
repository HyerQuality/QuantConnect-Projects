SELECT
	dm.*, d.*
FROM
	dept_manager dm
CROSS JOIN
	departments d
WHERE
	d.dept_no = 'd009'
ORDER BY
	d.dept_no;