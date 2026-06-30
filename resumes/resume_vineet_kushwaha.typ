#set page(
  paper: "us-letter",
  margin: (x: 0.35in, top: 0.22in, bottom: 0.22in),
)

#set text(
  font: "Liberation Sans",
  size: 9.5pt,
  fill: rgb("#1d1d1d"),
)

#set par(justify: true, leading: 0.496em) // original is 0.4 had to test the limits.

// Style links globally
#show link: set text(fill: rgb("#0f4c81"))

// Style headers to be visually identical but structurally clean for ATS
#show heading: it => block(
  width: 100%,
  stroke: (bottom: 0.5pt + rgb("#b0b0b0")),
  inset: (bottom: 3.5pt),
  above: 15pt, 
  below: 5pt,
)[
  #text(size: 10pt, weight: "bold", fill: rgb("#0f4c81"))[#upper(it.body)]
]

// List styling
#set list(marker: ([•],), indent: .5em ,body-indent: .5em, spacing: 0.8em)

// Entry helper function
#let entry(
  title: "",
  subtitle: "",
  date: "",
) = {
  block(width: 100%, breakable: false)[
    #grid(
      columns: (1fr, auto),
      [
        #text(weight: "bold")[#title]
        #if subtitle != "" [
          #text(weight: "regular")[ --- #subtitle]
        ]
      ],
      [
        #text(weight: "regular")[#date]
      ]
    )
  ]
}

// Header
#align(left)[
  #text(size: 19pt, weight: "bold", fill: rgb("#0f4c81"))[Vineet Kushwaha] \
  #v(1pt)
  #text(size: 8.8pt)[
    Bengaluru, India |
    #link("mailto:vineetkushwaha6325@gmail.com")[vineetkushwaha6325\@gmail.com] |
    #link("https://www.linkedin.com/in/vineet-k09/")[linkedin.com/in/vineet-k09] |
    #link("https://github.com/vineet-k09/")[github.com/vineet-k09] |
    #link("https://vineetnotfound.vercel.app/")[vineetnotfound.vercel.app]
  ]
]
#v(2pt)

= About
Backend-focused software engineer specialized in designing scalable APIs, containerized microservices, and automated data pipelines. Experienced in query performance tuning, and integrating generative AI features and workflows across GCP and real-time client systems.

= Experience
#entry(
  title: "Data Analyst",
  subtitle: "Vodafone Intelligent Solutions",
  date: "Jan 2026 – July 2026",
)
- Engineered an automated data-ingestion and validation pipeline to process 400K+ monthly multi-market records, replacing legacy manual workflows with scheduled Excel scripts and reducing human intervention by 90%.
- Designed and deployed a containerized Node.js/Express microservice on Google Cloud Run within a 3-service mesh, implementing secure server-to-server communication using GCP service accounts and IAM user verification.
- Integrated generative AI features utilizing Vertex AI (Gemini 2.5 Flash Lite), designing an Express API pipeline that streams interaction metadata into BigQuery through a React client for near-real-time user engagement analytics.

#entry(
  title: "Full Stack Developer Intern",
  subtitle: "Infosys Springboard",
  date: "Oct 2025 – Dec 2025",
)
- Developed secure RESTful API endpoints in Node.js/Express with JWT-based stateful authentication, implementing secure HttpOnly cookies, password hashing (bcrypt), and schema-level validation using Zod.
- Led a team of 4 developers, driving technical decisions, task allocation, project planning, and feature delivery across frontend and backend modules.
- Designed and integrated full-stack features using React.js, Node.js, Express, and MongoDB, collaborating across the development lifecycle from requirement gathering to deployment.

= Projects
#entry(
  title: "SAC Commenting – Context-Aware Analytics Collaboration Tool",
  date: "Mar 2026 - Jun 2026",
)
- Developed an embedded React widget that consumed SAP Analytics Cloud postMessage events to capture dashboard context, filter selections, and user interactions for downstream workflows.
- Built Express.js APIs and data persistence services to store comments alongside dashboard context metadata, enabling retrieval and contextual rendering within SAP Analytics Cloud dashboards.
- Integrated Vertex AI services to generate contextual summaries and rewrites of dashboard comments while preserving relevant business metadata through structured JSON outputs.
- Automated dashboard snapshot generation using Puppeteer, capturing live dashboard views and forwarding screenshots to backend AI services for contextual reporting and insight generation.

#entry(
  title: "iConnect 2.0 – AI-Powered Enterprise Learning Platform",
  date: "Apr 2026 - Jun 2026",
)
- Architected a microservice topology separating a Node.js/Express gateway (authentication and user management) from a FastAPI AI inference agent, containerized and deployed on Google Cloud Run.
- Secured inter-service communication using OAuth 2.0 and Google-signed service account credentials, building structured query generation engines targeting BigQuery.
- Developed a caching layer that persists generated AI recommendations in a transactional cache, reducing redundant Vertex AI model invocations by 35% and saving 200K+ daily tokens.

#entry(
  title: "Real-Time Hand Gesture MIDI Synthesizer",
  date: "Mar 2025 – Sep 2025",
)
#v(1pt)
#text(size: 8.5pt)[
  Link: #link("https://github.com/shyamkrishnabnair/hand-gesture-recognition-mediapipe-main")[github.com/shyamkrishnabnair/hand-gesture-recognition-mediapipe-main]
]
- Developed a rule-based coordinate geometry classifier utilizing MediaPipe hand landmark vectors to recognize 10 finger-count gestures and real-time pinch triggers with zero ML model execution overhead.
- Optimized browser execution to achieve 60 FPS by implementing canvas frame skipping and offloading audio synthesis to multi-threaded Web Workers, minimizing audio latency buffer to ≈12 ms.

= Technical Skills
*Languages:* Python, JavaScript, TypeScript, Java #h(1.2em) *Tools:* Git, GitHub, Linux (Fedora) \ 
*Frontend:* ReactJS, Vite, NextJS, Angular #h(1.2em) *Databases:* PostgreSQL, MongoDB, Redis, MySQL, BigQuery \
*Backend:* Node.js, Express.js, Django, FastAPI, REST APIs, JWT Authentication, Prisma, Microservices \
*Cloud/DevOps:* GCP, Docker, CI/CD (GitHub Actions) #h(1.2em) 

= Education
#entry(
  title: "B.E. CSE (Data Science)",
  subtitle: "Acharya Institute of Technology",
  date: [CGPA: 8.7 | June 2026],
)
- *Content Head:* Innovation and Entrepreneurship Development Cells (IEDC) Acharya Institute of Technology