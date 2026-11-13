const express = require("express");

const app = express();
const port = process.env.PORT || 8000;

app.use(express.json());

app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "{{PROJECT_SLUG}}"
  });
});

app.get("/", (req, res) => {
  res.json({
    message: "Welcome to {{PROJECT_NAME}}"
  });
});

app.listen(port, "0.0.0.0", () => {
  console.log("{{PROJECT_SLUG}} listening on port " + port);
});
