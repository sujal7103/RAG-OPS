export const demoDataset = {
  name: "React Demo Dataset",
  documents: [
    {
      doc_id: "doc_api",
      source: "api-guide.md",
      content:
        "RAG-OPS exposes a FastAPI service for datasets, benchmark runs, provider credentials, and historical reports.",
    },
    {
      doc_id: "doc_metrics",
      source: "ops-guide.md",
      content:
        "Prometheus metrics track request latency, benchmark attempts, retries, and dead letters for failed run execution.",
    },
    {
      doc_id: "doc_storage",
      source: "storage-guide.md",
      content:
        "Completed run artifacts can be uploaded to S3-compatible object storage so reports survive worker restarts and local disk loss.",
    },
  ],
  queries: [
    { query_id: "q_api", query: "What service handles benchmark runs?" },
    { query_id: "q_ops", query: "How are retries and dead letters monitored?" },
    { query_id: "q_storage", query: "Where should completed artifacts be stored?" },
  ],
  ground_truth: {
    q_api: ["doc_api"],
    q_ops: ["doc_metrics"],
    q_storage: ["doc_storage"],
  },
};
