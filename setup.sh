#!/bin/bash

# Flushing screen
clear
echo "Checking Python installation..."

# Checking python installation and version
version=$(python -V 2>&1 | grep -Po '(?<=Python )(.+)')
if [[ -z "$version" ]]
then
    echo -e "\e[31mPython is not installed. Please install Python 3.7 or newer.\e[0m"
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

pi_ver =$(pip -V 2>&1 | grep -Po '(?<=pip )(\d+\.)?(\d+\.)?(\*|\d+)')
if [[ -z "$pi_ver" ]]
then
    echo -e "\e[31mPip not installed. Please install pip for python 3.\e[0m"
    exit
fi 
# Install python modules with pip
echo "Installation of python modules..."
pip install -Uq -r requirements.txt
echo "Done."

# Creating additionnal files for the bot to run
echo "Creating new files..."
if [[! -e first ]] then echo [] > first; fi
if [[! -e second ]] then echo [] > second; fi
if [[! -e token ]] then touch token; fi
if [[! -e chans ]] then touch chans; fi
if [[! -e new ]] then touch new; fi
if [[! -e reminder ]] then touch reminder; fi
echo "Done."

# Launching option
echo "Do you want to launch the bot now ? [O/n]"
read choice
if [[ $choice == "n" ]]
then
    exit
else 
    ./main.py>journal.log &
fi
echo "Done."
