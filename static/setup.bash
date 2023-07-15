#!/bin/bash
yum update -y
yum install httpd -y

service httpd start
chkconfig httpd on

wget https://gitlab.surrey.ac.uk/vn00197/comm034/-/raw/main/aws_ec2.py -P /var/www/cgi-bin
chmod +x /var/www/cgi-bin/aws_ec2.py


