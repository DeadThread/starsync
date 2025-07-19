StarSync

StarSync is a lightweight Flask web app designed to automatically assign star ratings to unrated music tracks in your Plex libraries. It addresses an issue where Plex’s Library Radio does not properly include unrated live music tracks. StarSync sets a base rating to ensure these tracks are recognized and included in your Library Radio mixes.
Features

- Automatically rates unrated tracks in your specified Plex music libraries

- Supports 1-star, 5-star, or 5-star half-step rating styles

- Configurable batch size and interval for rating operations

- Manual and webhook-triggered rating support

- Web interface for login, triggering ratings, resetting ratings, and changing settings

- Secure login with customizable username/password

- Live logging view in the web interface

- Runs easily via Docker Compose or directly with Python

Why StarSync?

Plex’s Library Radio can exclude unrated music tracks—especially live or obscure tracks you want included. Instead of manually rating thousands of songs, StarSync automatically assigns a default star rating to unrated tracks, improving your Library Radio experience by making sure all your music gets proper recognition.
Requirements

- Plex server with a valid API token

- Docker & Docker Compose (optional, recommended for ease)

- Python 3.8+ (if running without Docker)

Installation & Usage
1. Create a .env file in the project root directory

Before running StarSync, create a .env file with your custom configuration variables. For example:

    # Plex server connection info
    PLEX_URL=http://your-plex-server:32400
    PLEX_TOKEN=your_plex_token_here
    
    # Comma-separated list of library names to monitor/tag
    LIBRARY_NAME=Music
    
    # Rating style options: 1star, 5stars, or 5stars_half
    RATING_STYLE=5stars
    
    # Target rating value:
    # - For 1star: 0 or 1
    # - For 5stars or 5stars_half: 1.0 to 5.0
    TARGET_RATING=3.0
    
    # Override existing ratings? (true or false)
    OVERRIDE_RATING=False
    
    # Minutes between periodic batch triggers (0 disables periodic triggers)
    BATCH_INTERVAL_MINUTES=60
    
    # Number of tracks to process per batch trigger
    BATCH_SIZE=500
    
    # Login credentials for the web interface
    APP_USERNAME=your_username
    APP_PASSWORD=your_password
    
    # Flask secret key for session security
    FLASK_SECRET_KEY=replace_with_a_secure_random_key


    | Variable                 | Description                                                   | Default / Notes           |
    | ------------------------ | ------------------------------------------------------------- | ------------------------- |
    | PLEX\_URL                | URL of your Plex server                                       | Required                  |
    | PLEX\_TOKEN              | Your Plex API token                                           | Required                  |
    | LIBRARY\_NAME            | Comma-separated Plex music libraries to monitor               | Required                  |
    | RATING\_STYLE            | Rating style: "1star", "5stars", or "5stars\_half"            | "5stars" recommended      |
    | TARGET\_RATING           | Target rating value (depends on rating style)                 | 3.0                       |
    | OVERRIDE\_RATING         | Override existing ratings? "true" or "false"                  | false                     |
    | BATCH\_INTERVAL\_MINUTES | Minutes between periodic batch runs. Set 0 to disable         | 60                        |
    | BATCH\_SIZE              | Number of tracks processed per batch                          | 500                       |
    | APP\_USERNAME            | Username for the web UI login                                 | Required                  |
    | APP\_PASSWORD            | Password for the web UI login                                 | Required                  |
    | FLASK\_SECRET\_KEY       | Secret key for Flask sessions (set to a secure random string) | "supersecretkey" fallback |

    
2. Run with Docker Compose (recommended)

No need to clone the repo locally — Docker Compose will pull the code directly from GitHub.

Create a docker-compose.yml file in your project directory with the following content:

    services:
      starsync:
        build:
          context: https://github.com/DeadThread/starsync.git
        container_name: starsync
        ports:
          - "5454:5454"
        environment:
          PLEX_URL: "${PLEX_URL}"
          PLEX_TOKEN: "${PLEX_TOKEN}"
          LIBRARY_NAME: "${LIBRARY_NAME}"
          RATING_STYLE: "${RATING_STYLE}"
          TARGET_RATING: "${TARGET_RATING}"
          OVERRIDE_RATING: "${OVERRIDE_RATING}"
          BATCH_INTERVAL_MINUTES: "${BATCH_INTERVAL_MINUTES}"
          BATCH_SIZE: "${BATCH_SIZE}"
          APP_USERNAME: "${APP_USERNAME}"
          APP_PASSWORD: "${APP_PASSWORD}"
          FLASK_SECRET_KEY: "${FLASK_SECRET_KEY}"
          PUID: "1000"
          PGID: "1000"
        volumes:
          - ./logs:/app/logs
          - ./config:/app/config
        restart: unless-stopped

Then run:

    docker-compose up -d

The app will be accessible at http://localhost:5454 (replace localhost with your server IP if running remotely).

3. (Optional) Clone the repository for running locally with Python

If you want to run StarSync using Python directly (without Docker), clone the repo and enter the directory:

git clone https://github.com/DeadThread/starsync.git
cd starsync

4. Run with Python directly (development or no Docker)

Make sure Python 3.8+ is installed. Then install dependencies:

pip install -r requirements.txt

Make sure your .env file is in the project root.

Start the app:

python app.py

The app will be accessible at http://localhost:5454



Features

- Login: Secure web interface access requiring username and password as configured in your .env file.

- Trigger: Manually start the rating process for all unrated tracks in your selected libraries.

- Trigger Last Batch: Manually trigger rating for the most recent batch of tracks based on your batch size setting.

- Settings: Easily update monitored libraries, rating style and value, override preferences, and batch interval — all through the web UI.

- Reset Ratings: Clear all existing user ratings on tracks, allowing you to start fresh if needed.

- Live Log: View real-time, detailed logs of all rating operations directly in the web interface for monitoring and troubleshooting.

How It Works

StarSync connects to your Plex server and retrieves the specified music libraries. It identifies tracks without user ratings and assigns a configured star rating when triggered — whether manually, by Plex webhook events, or on a scheduled interval. This ensures unrated tracks are included and properly recognized in Plex Library Radio.

You can choose to only rate unrated tracks or override existing ratings with your preferred value.
Plex Webhook Integration

StarSync supports Plex webhooks to automate the rating process when new music is added. To enable this, configure your Plex server to send webhook notifications to:

http://your-starsync-server:5454/plex-webhook

Upon receiving relevant events, StarSync will automatically rate new tracks according to your settings.
Logging

All activity is logged and saved in the logs directory. Logs are also streamed live to the web interface for easy real-time monitoring and troubleshooting.
Contributing

Contributions, suggestions, and bug reports are very welcome! Feel free to open issues or submit pull requests on the GitHub repository.
License

StarSync is released under the MIT License.
