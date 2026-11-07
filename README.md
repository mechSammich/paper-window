# paper-window
An e-paper window into the hivemind

# project details
This project allows the user to use a raspberry pi zero w with an e-paper display and a 5 button interface to view and interact with the task items on any local silverbullet note pages that contain the tag "paper-window" in their frontmatter. 

## hardware list
1. raspberry pi zero w v1.1
2. waveshare 2.13" black and white e-paper display hat (V4)
3. tactile button inputs on GPIO for the following functions
   1. next task
   2. previous task
   3. toggle task state
   4. next page
   5. previous page

## software requirements
1. toml config file for easy setup
2. config to contain server url and arguments for password authentication
3. queries target silverbullet server for pages with "paper-window" in frontmatter (tell me if this is not possible)
4. allows user to navigate between pages int this list
5. allows user to scroll through tasks on the current page
6. allows user to toggle task status on selected task
7. displays current page name in upper left of screen
8. font size that allows approximately 26 chars per row
