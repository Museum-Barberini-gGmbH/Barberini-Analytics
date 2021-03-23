#!/bin/bash
set -e

sudo docker network create barberini_analytics_database_network
sudo usermod -aG docker "$USER"
echo "Please reboot for user group changes to take effect"
read -r -n 1 -p "Reboot now? [y/n]" -s && echo
if [[ "$REPLY" == "y" ]]
    then sudo reboot
fi
