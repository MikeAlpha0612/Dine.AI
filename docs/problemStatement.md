# Problem Statement: AI-Powered Restaurant Recommendation System

## Overview

Build an **AI-powered restaurant recommendation service** inspired by Zomato. The system should suggest restaurants based on user preferences by combining structured restaurant data with a Large Language Model (LLM) to produce personalized, human-like recommendations.

## Objective

Design and implement an application that:

- Accepts user preferences such as location, budget, cuisine, and minimum rating
- Uses a real-world restaurant dataset as the source of truth
- Leverages an LLM to generate personalized recommendations with clear reasoning
- Presents results in a clear, user-friendly format

## System Workflow

### 1. Data Ingestion

- Load and preprocess the Zomato dataset from Hugging Face: [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation)
- Extract relevant fields, including restaurant name, location, cuisine, cost, and rating

### 2. User Input

Collect user preferences:

| Preference | Examples |
|------------|----------|
| Location | Delhi, Bangalore |
| Budget | Low, medium, high |
| Cuisine | Italian, Chinese |
| Minimum rating | e.g., 4.0+ |
| Additional preferences | Family-friendly, quick service |

### 3. Integration Layer

- Filter and prepare restaurant data based on user input
- Pass structured results into an LLM prompt
- Design a prompt that helps the LLM reason about and rank options

### 4. Recommendation Engine

Use the LLM to:

- Rank restaurants by relevance to the user's preferences
- Explain why each recommendation is a good fit
- Optionally summarize the top choices

### 5. Output Display

Present the top recommendations in a user-friendly format, including:

- Restaurant name
- Cuisine
- Rating
- Estimated cost
- AI-generated explanation

## Expected Outcome

A working recommendation flow where users enter preferences, the system filters relevant restaurants from the dataset, the LLM ranks and explains the best matches, and the user receives actionable, well-reasoned suggestions.
