#set page(
  paper: "us-letter",
  margin: (x: 0.35in, top: 0.22in, bottom: 0.22in),
)

#set text(
  font: "Liberation Sans",
  size: 9.5pt,
  fill: rgb("#1d1d1d"),
)

#set par(justify: true, leading: 0.496em)

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

// ─── Header — Replace with your own details ───────────────────────────────────
#align(left)[
  #text(size: 19pt, weight: "bold", fill: rgb("#0f4c81"))[Jane Doe] \
  #v(1pt)
  #text(size: 8.8pt)[
    Bengaluru, India |
    #link("mailto:jane.doe@example.com")[jane.doe\@example.com] |
    #link("https://www.linkedin.com/in/jane-doe/")[linkedin.com/in/jane-doe] |
    #link("https://github.com/jane-doe/")[github.com/jane-doe] |
    #link("https://janedoe.dev/")[janedoe.dev]
  ]
]
#v(2pt)

= About
Backend-focused software engineer specializing in designing scalable APIs, containerized microservices, and automated data pipelines. Experienced in query performance tuning, integrating generative AI features, and building cloud-native systems on GCP.

= Experience
#entry(
  title: "Software Engineer",
  subtitle: "Acme Corp",
  date: "Jan 2026 – Present",
)
- Engineered an automated data-ingestion and validation pipeline processing 500K+ monthly records, reducing manual intervention by 90%.
- Deployed containerized microservices on Google Cloud Run within a multi-service mesh, securing server-to-server communication using GCP service accounts and IAM.
- Integrated Vertex AI (Gemini 2.5 Flash) to stream interaction metadata into BigQuery for near-real-time analytics.

#entry(
  title: "Backend Developer Intern",
  subtitle: "Startup XYZ",
  date: "Oct 2025 – Dec 2025",
)
- Developed RESTful API endpoints in Node.js/Express with JWT-based authentication, implementing HttpOnly cookies, bcrypt password hashing, and Zod validation.
- Led a team of 4 developers, coordinating sprint planning, code reviews, and feature delivery.
- Built full-stack features using React.js, Node.js, Express, and MongoDB across the entire development lifecycle.

= Projects
#entry(
  title: "Analytics Collaboration Tool — Context-Aware Commenting",
  date: "Mar 2026 – Jun 2026",
)
- Built an embedded React widget capturing dashboard context and filter state via postMessage events for downstream workflows.
- Developed Express.js APIs persisting comments alongside dashboard metadata for contextual retrieval and rendering.
- Integrated Vertex AI to generate contextual summaries of dashboard comments using structured JSON outputs.
- Automated dashboard snapshots with Puppeteer, forwarding screenshots to backend AI services for insight generation.

#entry(
  title: "AI-Powered Enterprise Learning Platform",
  date: "Apr 2026 – Jun 2026",
)
- Architected a microservice topology with a Node.js/Express gateway and FastAPI AI inference agent, deployed on Google Cloud Run.
- Secured inter-service communication using OAuth 2.0 and Google-signed service account credentials.
- Built a caching layer reducing redundant Vertex AI invocations by 35%, saving 200K+ daily tokens.

#entry(
  title: "Real-Time Hand Gesture MIDI Synthesizer",
  date: "Mar 2025 – Sep 2025",
)
#v(1pt)
#text(size: 8.5pt)[
  Link: #link("https://github.com/example-user/hand-gesture-midi")[github.com/example-user/hand-gesture-midi]
]
- Implemented a rule-based classifier using MediaPipe hand landmark vectors to recognize 10 gesture types with zero ML model overhead.
- Achieved 60 FPS browser execution via canvas frame skipping and Web Worker audio synthesis, minimizing latency to ≈12 ms.

= Technical Skills
*Languages:* Python, JavaScript, TypeScript, Java #h(1.2em) *Tools:* Git, GitHub, Linux \
*Frontend:* ReactJS, Vite, NextJS, Angular #h(1.2em) *Databases:* PostgreSQL, MongoDB, Redis, MySQL, BigQuery \
*Backend:* Node.js, Express.js, Django, FastAPI, REST APIs, JWT Authentication, Prisma, Microservices \
*Cloud/DevOps:* GCP, Docker, CI/CD (GitHub Actions) #h(1.2em)

= Education
#entry(
  title: "B.E. Computer Science (Data Science)",
  subtitle: "Example University",
  date: [CGPA: 8.5 | June 2026],
)
- *Leadership Role:* Innovation and Entrepreneurship Development Cell (IEDC)
