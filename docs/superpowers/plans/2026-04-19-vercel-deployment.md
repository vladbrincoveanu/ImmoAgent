# Vercel Deployment Guide

## Prerequisites
- Vercel account connected to GitHub
- MongoDB Atlas cluster (or public-facing MongoDB)

## Steps

1. **Push dashboard to GitHub**
   The `dashboard/` folder should be in the repo root.

2. **Connect to Vercel**
   - Go to vercel.com → New Project
   - Import the repo
   - Set root directory to `dashboard/`
   - Add environment variable: `MONGODB_URI` = your Atlas connection string

3. **Deploy**
   - Vercel auto-detects Next.js
   - Deploy — should complete in ~2 minutes

4. **Custom Domain (optional)**
   - Add domain in Vercel project settings

## MongoDB Atlas Setup

If using MongoDB Atlas (free tier M0):
1. Create cluster at atlas.mongodb.com
2. Add IP `0.0.0.0/0` to Network Access
3. Create database user
4. Get connection string: `mongodb+srv://user:pass@cluster.mongodb.net/immo`
5. Set `MONGODB_URI` in Vercel env vars