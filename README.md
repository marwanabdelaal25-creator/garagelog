# garagelog

Vehicle maintenance garage CLI I wrote after missing an oil change by six weeks
because the dealership sticker peeled off and my Notes app thought "5W-30" was
a Wi-Fi password.

One JSON file (`garage.json`) on disk. Log services, track mileage, note part
numbers, and grep for "Camry" at 7am without another app subscription.

## What it does

- Track vehicles with purchase date, make profile, and bay placement
- Log service records (type, labor hours, parts cost, odometer, notes)
- Inspection notes and issue reports when something sounds wrong
- Odometer history and mileage trends in the garage
- Weekly service stats, streaks, seasonal maintenance calendars
- Import from Carfax CSV and Drivvo exports
- Reminders when a vehicle is due for service

## What it doesn't do

- Live OBD-II Bluetooth dongles or dealership API sync
- AI damage assessment from photos
- Multi-user fleet management at enterprise scale

## Quick start

```bash
pip install .
garagelog init ~/cars/garage.json
garagelog add-vehicle --name "Daily Camry" --purchase 2020-03-01 --make toyota
garagelog service veh001 --type oil_change --hours 1.5 --parts 45
garagelog stats --week
```

## Author

Marwan Helmy — marwanabdelaal25@gmail.com

MIT license. Side project, Oct 2024–present.
