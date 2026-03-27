# --- Build stage ---
FROM node:18-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --only=production

# --- Production stage ---
FROM node:18-alpine

# Create a non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy only production dependencies and app code
COPY --from=builder /app/node_modules ./node_modules
COPY app.js ./

USER appuser

# Cloud Run injects PORT; default to 8080
ENV PORT=8080
EXPOSE 8080

CMD ["node", "app.js"]
