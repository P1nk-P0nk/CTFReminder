#!/bin/bash

# Flushing screen
clear
echo "Checking Python installation..."

# Checking python installation and version
version=$(python -V 2>&1 | grep -Po '(?<=Python )(.+)')
if [[ -z "$version" ]]
then
    echo -e "\e[31mPython is not installed.\e[0m"
    exit
fi
parsedVersion=$(echo "${version//./}")
if [[ "$parsedVersion" -gt "370" ]]
then 
    echo -e "\e[92mValid version.\e[0m"
else
    echo -e "\e[31mPython <= 3.7.0 \nPlease update Python\e[0m"
    exit
fi

# Install python modules with pip
echo "Installation of python modules..."
pip install -Uq -r requirements.txt
echo "Done."

# Creating additionnal files for the bot to run
echo "Creating new files..."
echo [] > first
echo [] > second
touch chans
touch token
echo "Done."

# Launching option
echo "Do you want to launch the bot now ? [O/n]"
read choice
if [[ $choice == "n" ]]
then
    exit
else 
    ./main.py &
fi
echo "Done."
