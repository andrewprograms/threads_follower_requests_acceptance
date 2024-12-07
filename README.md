# Threads Follower Requests Acceptance App

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Disclaimer](#disclaimer)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Overview

The **Threads Follower Requests Acceptance App** is a Python-based tool that automates the process of accepting follower requests on [Threads.net](https://www.threads.net). It leverages a local Flask web server to provide a user-friendly interface for configuring and initiating the automation process. Once started, the app opens a browser window where you can manually log in to Threads.net. After successful authentication, the script navigates to your follower requests page and programmatically accepts a specified number of follower requests.

## Features

- **Local Web Interface:** Easily configure the number of follower requests to accept and set delay intervals.
- **Automated Browser Control:** Utilizes Selenium WebDriver to interact with Threads.net.
- **Manual Authentication:** Requires manual login and 2FA completion for secure access.
- **In-App Logging:** View real-time logs of the automation process directly within the web interface.
- **Customizable Delays:** Introduce human-like delays between actions to mimic natural behavior.

## Prerequisites

Before you begin, ensure you have met the following requirements:

- **Operating System:** Windows, macOS, or Linux
- **Python:** Version 3.7 or higher
- **Google Chrome Browser:** Installed on your system

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/threads-follower-acceptor.git
   cd threads-follower-acceptor
