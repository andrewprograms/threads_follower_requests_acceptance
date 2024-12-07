package main

import (
	"bytes"
	"context"
	"fmt"
	"html/template"
	"log"
	"math/rand"
	"net/http"
	"os/exec"
	"strconv"
	"sync"
	"time"

	"github.com/tebeka/selenium"
)

const (
	// Base URLs
	LOGIN_URL          = "https://www.threads.net/login/"
	MAIN_URL           = "https://www.threads.net/"
	FOLLOW_REQUESTS_URL = "https://www.threads.net/activity/requests"

	// Default configuration
	DEFAULT_MAX_REQUESTS = 1
	DEFAULT_DELAY_MIN    = 2
	DEFAULT_DELAY_MAX    = 6

	// Explicit Wait time in seconds
	EXPLICIT_WAIT = 90
)

// Global state
var (
	processRunning   bool
	processCompleted bool

	logBuffer bytes.Buffer
	logMu     sync.Mutex

	tmpl *template.Template
)

var htmlTemplate = `
<!doctype html>
<html lang="en">
<head>
    <title>Threads Follower Requests Acceptance</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; }
        .container { max-width: 700px; margin: auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0, 0, 0, 0.1); }
        h1, h2, h3 { text-align: center; color: #333; }
        form { display: flex; flex-direction: column; gap: 15px; }
        label { font-weight: bold; color: #555; }
        input[type="number"] {
            padding: 10px; 
            border: 1px solid #ccc; 
            border-radius: 4px;
            font-size: 16px;
        }
        button {
            padding: 12px; 
            background-color: #007bff;
            border: none; 
            border-radius: 4px;
            color: #fff; 
            font-size: 16px; 
            cursor: pointer;
            transition: background-color 0.3s ease;
        }
        button:hover { background-color: #0056b3; }
        .disclaimer {
            background: #fff3cd; 
            padding: 15px; 
            border-radius: 4px;
            color: #856404;
            margin-bottom: 25px;
            border: 1px solid #ffeeba;
        }
        pre { background: #f8f9fa; padding: 15px; border-radius: 4px; overflow: auto; max-height: 400px; }
        .logs-container { margin-top: 20px; }
        .footer { text-align: center; margin-top: 30px; color: #888; font-size: 14px; }
        a { color: #007bff; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
<div class="container">
    <h1>Threads Follower Requests Acceptance</h1>
    <div class="disclaimer">
        <strong>Disclaimer:</strong> This script may violate Threads' Terms of Service. Use it at your own risk.
    </div>
    {{ if and (not .Running) (not .Completed) }}
    <!-- Input form for max requests and delay times -->
    <h2>Set Your Parameters</h2>
    <p>When you start the process, a browser will open and take you to the Threads.net login page. Please log in manually.</p>
    <form method="POST" action="/run">
        <label for="max_requests">Max Requests to Accept (Default: {{.DefaultMax}}):</label>
        <input type="number" name="max_requests" value="{{.DefaultMax}}" min="1" required>

        <label for="delay_min">Minimum Delay Time in Seconds (Default: {{.DefaultDelayMin}}):</label>
        <input type="number" name="delay_min" value="{{.DefaultDelayMin}}" min="1" required>

        <label for="delay_max">Maximum Delay Time in Seconds (Default: {{.DefaultDelayMax}}):</label>
        <input type="number" name="delay_max" value="{{.DefaultDelayMax}}" min="1" required>

        <button type="submit">Start Process</button>
    </form>
    {{ else if .Running }}
    <h2>Process is Running...</h2>
    <p>Please log in to Threads.net in the opened browser if you haven't already. Complete any 2FA steps if prompted. Once logged in, the script will proceed automatically.</p>
    <div class="logs-container">
        <form action="/logs">
            <button type="submit">Refresh Logs</button>
        </form>
        <pre>{{.Logs}}</pre>
    </div>
    {{ else if .Completed }}
    <h2>Process Completed!</h2>
    <p>Below are the logs:</p>
    <div class="logs-container">
        <pre>{{.Logs}}</pre>
    </div>
    <a href="/">Back to Home</a>
    {{ end }}
</div>
<div class="footer">
    Version: 0.03
</div>
</body>
</html>
`

func init() {
	var err error
	tmpl, err = template.New("page").Parse(htmlTemplate)
	if err != nil {
		panic(err)
	}
	rand.Seed(time.Now().UnixNano())
}

func main() {
	// Optionally: open browser to http://127.0.0.1:5000 (uncomment if desired)
	go func() {
		time.Sleep(2 * time.Second)
		exec.Command("open", "http://127.0.0.1:5000").Start() // macOS; adjust for Windows/Linux if needed
	}()

	http.HandleFunc("/", homeHandler)
	http.HandleFunc("/run", runHandler)
	http.HandleFunc("/logs", logsHandler)

	fmt.Println("Starting server on :5000")
	if err := http.ListenAndServe(":5000", nil); err != nil {
		log.Fatal(err)
	}
}

func homeHandler(w http.ResponseWriter, r *http.Request) {
	logMu.Lock()
	logs := logBuffer.String()
	logMu.Unlock()

	data := map[string]interface{}{
		"Running":          processRunning,
		"Completed":        processCompleted,
		"DefaultMax":       DEFAULT_MAX_REQUESTS,
		"DefaultDelayMin":  DEFAULT_DELAY_MIN,
		"DefaultDelayMax":  DEFAULT_DELAY_MAX,
		"Logs":             logs,
	}
	tmpl.Execute(w, data)
}

func logsHandler(w http.ResponseWriter, r *http.Request) {
	logMu.Lock()
	logs := logBuffer.String()
	logMu.Unlock()

	data := map[string]interface{}{
		"Running":          processRunning,
		"Completed":        processCompleted,
		"DefaultMax":       DEFAULT_MAX_REQUESTS,
		"DefaultDelayMin":  DEFAULT_DELAY_MIN,
		"DefaultDelayMax":  DEFAULT_DELAY_MAX,
		"Logs":             logs,
	}
	tmpl.Execute(w, data)
}

func runHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Redirect(w, r, "/", http.StatusSeeOther)
		return
	}

	if processRunning {
		logMessage("Process is already running. Please wait until it completes.")
		http.Redirect(w, r, "/", http.StatusSeeOther)
		return
	}

	maxRequestsStr := r.FormValue("max_requests")
	delayMinStr := r.FormValue("delay_min")
	delayMaxStr := r.FormValue("delay_max")

	maxRequests := parseOrDefault(maxRequestsStr, DEFAULT_MAX_REQUESTS)
	delayMin := parseOrDefault(delayMinStr, DEFAULT_DELAY_MIN)
	delayMax := parseOrDefault(delayMaxStr, DEFAULT_DELAY_MAX)

	if delayMin > delayMax {
		logMessage(fmt.Sprintf("Minimum delay (%d) is greater than maximum delay (%d). Swapping values.", delayMin, delayMax))
		delayMin, delayMax = delayMax, delayMin
	}

	logMu.Lock()
	logBuffer.Reset()
	logMu.Unlock()

	// Run in background
	go func() {
		processRunning = true
		processCompleted = false
		runScript(maxRequests, delayMin, delayMax)
		processRunning = false
		processCompleted = true
	}()

	http.Redirect(w, r, "/", http.StatusSeeOther)
}

func parseOrDefault(s string, def int) int {
	v, err := strconv.Atoi(s)
	if err != nil || v < 1 {
		return def
	}
	return v
}

func logMessage(msg string) {
	logMu.Lock()
	defer logMu.Unlock()
	t := time.Now().Format("2006-01-02 15:04:05")
	logBuffer.WriteString(fmt.Sprintf("[%s] INFO: %s\n", t, msg))
}

// runScript performs the main automation routine
func runScript(maxRequests, delayMin, delayMax int) {
	logMessage("Starting the automation process...")

	logMessage(fmt.Sprintf("Configured Delay Times - Min: %d seconds, Max: %d seconds", delayMin, delayMax))

	// Set up Selenium
	const (
		seleniumURL = "http://localhost:9515/wd/hub" // Change if needed
	)
	caps := selenium.Capabilities{"browserName": "chrome"}
	// Add chrome options if desired
	chromeArgs := []string{
		"--disable-infobars",
		"--disable-extensions",
		"--disable-gpu",
		"--no-sandbox",
		"--start-maximized",
	}
	caps.AddChrome(selenium.Capabilities{"args": chromeArgs})

	wd, err := selenium.NewRemote(caps, seleniumURL)
	if err != nil {
		logMessage(fmt.Sprintf("Failed to connect to Selenium: %v", err))
		return
	}
	defer wd.Quit()

	// 1. Navigate to login page
	logMessage(fmt.Sprintf("Navigating to Threads.net login page: %s", LOGIN_URL))
	if err := wd.Get(LOGIN_URL); err != nil {
		logMessage(fmt.Sprintf("Failed to load login page: %v", err))
		return
	}
	humanDelay(delayMin, delayMax)

	// 2. Wait for manual login
	if err := waitForManualLogin(wd, EXPLICIT_WAIT); err != nil {
		logMessage("Login was not detected in time. Please ensure you logged in.")
		return
	}

	// 3. Navigate to follower requests page
	if err := navigateToRequests(wd, delayMin, delayMax); err != nil {
		logMessage(fmt.Sprintf("Error navigating to requests: %v", err))
		return
	}

	// 4. Accept requests
	acceptFollowerRequests(wd, maxRequests, delayMin, delayMax)

	logMessage("Browser closed. Automation process finished.")
}

func humanDelay(minDelay, maxDelay int) {
	d := time.Duration(minDelay+rand.Intn(maxDelay-minDelay+1)) * time.Second
	logMessage(fmt.Sprintf("Sleeping for %.2f seconds to mimic human behavior.", d.Seconds()))
	time.Sleep(d)
}

func waitForManualLogin(wd selenium.WebDriver, timeout int) error {
	logMessage("Waiting for manual login... Please complete login in the opened browser window.")
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout)*time.Second)
	defer cancel()

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return fmt.Errorf("timeout waiting for login")
		case <-ticker.C:
			url, err := wd.CurrentURL()
			if err == nil && url == MAIN_URL {
				logMessage("Detected successful login to Threads.net.")
				return nil
			}
		}
	}
}

func navigateToRequests(wd selenium.WebDriver, delayMin, delayMax int) error {
	logMessage(fmt.Sprintf("Navigating to follower requests page: %s", FOLLOW_REQUESTS_URL))
	if err := wd.Get(FOLLOW_REQUESTS_URL); err != nil {
		return err
	}

	// Wait until URL matches
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(EXPLICIT_WAIT)*time.Second)
	defer cancel()

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return fmt.Errorf("timeout waiting for requests page to load")
		case <-ticker.C:
			url, _ := wd.CurrentURL()
			if url == FOLLOW_REQUESTS_URL {
				logMessage("Successfully navigated to follower requests page.")
				humanDelay(delayMin, delayMax)
				return nil
			}
		}
	}
}

func acceptFollowerRequests(wd selenium.WebDriver, maxRequests, delayMin, delayMax int) {
	logMessage(fmt.Sprintf("Attempting to accept up to %d follower requests...", maxRequests))
	acceptedCount := 0

	for acceptedCount < maxRequests {
		confirmButtons, err := wd.FindElements(selenium.ByXPATH, "//div[normalize-space(text())='Confirm']")
		if err != nil {
			logMessage("No 'Confirm' buttons found. Possibly no more requests or page changed.")
			break
		}

		if len(confirmButtons) == 0 {
			logMessage("No 'Confirm' buttons found.")
			break
		}

		for _, btn := range confirmButtons {
			if acceptedCount >= maxRequests {
				break
			}
			// Scroll into view
			wd.ExecuteScript("arguments[0].scrollIntoView(true);", []interface{}{btn})
			humanDelay(delayMin, delayMax)

			err = btn.Click()
			if err != nil {
				logMessage(fmt.Sprintf("Failed to click 'Confirm' button: %v", err))
				humanDelay(delayMin, delayMax)
				continue
			}
			acceptedCount++
			logMessage(fmt.Sprintf("Accepted follower request #%d", acceptedCount))
			humanDelay(delayMin, delayMax)
		}

		if acceptedCount < maxRequests {
			logMessage("Refreshing the follower requests list to find more 'Confirm' buttons.")
			wd.Refresh()
			humanDelay(delayMin, delayMax)
		}
	}

	logMessage(fmt.Sprintf("Completed accepting follower requests. Total accepted: %d", acceptedCount))
}
