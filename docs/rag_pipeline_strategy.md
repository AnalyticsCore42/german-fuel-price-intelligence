# Agentic RAG Pipeline: Data Tailoring Strategy

## Why Explicit Corporate Mapping is Crucial for RAG

By mapping raw, unstructured gas station brands exactly to their parent umbrellas, the data is explicitly tailored for natural language questions. 

If a user asks the Streamlit Chatbot:
> *"What is the difference in pricing strategy between the major agricultural cooperatives and the big oil companies during the 2026 Tankrabatt?"*

The LangChain Polars tool will look at the explicit schema (`corporate_group` column) and see `Agricultural Co-ops (Raiffeisen/BayWa)` and `BP (Aral)`. 

The agent instantly knows how to write the correct `GROUP BY` SQL/Polars query to compare them. 

### Key Benefit
This approach **completely removes the LLM's burden** of having to dynamically memorize or guess which of the 100+ raw German fuel brands belong to which sector. By solidifying the "Ground Truth" of corporate structures inside the ETL process, we eliminate AI hallucination regarding market segmentation.
