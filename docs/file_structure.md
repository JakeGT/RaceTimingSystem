
# Repository Layout and Test/CI Setup

## Repository Structure

The repository is structured as follows:

```
├── LICENSE
├── README.md
├── bib-detector
│   ├── best.pt
│   ├── bib-detector-images.py
│   ├── bib-detector.py
│   ├── requirements.txt
│   ├── website_api.py
│   └── website_dummy.py
├── docs
│   ├── architecture
│   │   ├── README.md
│   │   └── runningsysdiag.png
│   ├── db_schema.md
│   ├── decisions
│   │   └── licence-decision.md
│   ├── description_requirements_and_plan.md
│   ├── development_environment.md
│   ├── ethical_and_legal_considerations.md
│   ├── gantt.xlsx
│   └── interim_presentation.pdf
├── file_structure.txt
├── inventory.xlsx
├── logs
│   └── app.log
├── package-lock.json
├── package.json
├── playwright.config.ts
├── requirements.txt
├── running
│   ├── app
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── forms.py
│   │   ├── middleware.py
│   │   ├── migrations
│   │   ├── models.py
│   │   ├── templates
│   │   ├── tests.py
│   │   ├── urls.py
│   │   ├── utils
│   │   └── views.py
│   ├── db.sqlite3
│   ├── examples
│   ├── logs
│   ├── manage.py
│   ├── requirements.txt
│   └── running
├── scripts
│   └── image-upload.py
├── tests
│   ├── authenticated.spec.ts
│   ├── dashboard.spec.ts
│   ├── landing.spec.ts
│   ├── login.spec.ts
│   └── register.spec.ts
└── tests-examples
    └── demo-todo-app.spec.ts
```

## Description

- **`bib-detector/`**: Contains the bib detector client that is run on the machine locally at the race.
- **`running/`**: Main Django application including views, templates, and models.
- **`docs/`**: Project documentation including architecture diagrams and planning.
- **`scripts/`**: Utility scripts used during development or deployment.
- **`tests/` and `tests-examples/`**: Contain Playwright-based UI tests and examples.
- **`logs/`**: Application logging directory.
- **`LICENSE`, `README.md`**: Introductory documentation.

## Test and CI Setup

### Unit & Integration Testing

To run backend Django tests:

```bash
cd running
python manage.py test
```

### UI Tests (Playwright)

Ensure dependencies are installed:

```bash
npm install
```

To run all Playwright tests:

```bash
npx playwright test
```

To view test reports (after test run):

```bash
npx playwright show-report
```

### Continuous Integration

CI is handled through GitHub Actions. To simulate locally, install [act](https://github.com/nektos/act) and run:

```bash
act
```
