# **Roadmap: Scaling from Zero to Millions on GCP (Node.js Edition)**

This roadmap describes a series of hands-on tutorials designed to replace the legacy cloud-computing-gcp exercises. It follows the evolutionary path described in Chapter 1 of *System Design Interview* (Alex Xu), implemented entirely with Node.js and Google Cloud Platform technologies.

## **The "Evolutionary" Web App**

We will build an **"Image Processing & Storage App"** (Node.js/Express) that evolves:

* **v1:** Express app on a single VM storing images locally.  
* **v2:** App connects to Cloud SQL (MySQL) via Private IP.  
* **v3:** App uses GCS for storage and Memorystore (Redis) for metadata caching.  
* **v4:** App publishes to Pub/Sub for background processing via Cloud Run Functions.  
* **v5:** App is containerized and deployed to Cloud Run/GKE with full CI/CD.

## **Phase 1: The Monolith & Horizontal Growth**

### **Tutorial 1.1: The Single Server Setup**

* **Goal:** Host Web Server, App, and DB on one Compute Engine instance.  
* **Console Workflow:**  
  1. **Compute Engine \> VM Instances \> Create**.  
  2. Select e2-micro. Check **Allow HTTP traffic**.  
  3. SSH into the VM.  
  4. Install Node.js: curl \-fsSL https://deb.nodesource.com/setup\_18.x | sudo \-E bash \- && sudo apt-get install \-y nodejs.  
  5. Install DB: sudo apt install mariadb-server.  
* **GCLI Reference:**  
  gcloud compute instances create monolith-server \--zone=us-central1-a \--machine-type=e2-micro \--tags=http-server

### **Tutorial 1.2: Decoupling the Database**

* **Goal:** Separate state from the application server.  
* **Intermediate Steps:**  
  1. **VPC Network \> Private Service Access**: Click "Allocate IP Range" and "Create Connection" (Required for Cloud SQL Private IP).  
  2. **SQL \> Create Instance**: Select MySQL. In "Connections", uncheck "Public IP" and check "Private IP".  
* **Console Workflow:** 1\. Create Cloud SQL instance. 2\. Create a database app\_db and user app\_user. 3\. Update Node.js mysql2 config to the new Private IP.  
* **GCLI Reference:**  
  gcloud sql instances create app-db-instance \--tier=db-f1-micro \--region=us-central1 \--no-assign-ip \--network=default

### **Tutorial 1.3: Horizontal Scaling (MIGs & Load Balancing)**

* **Goal:** Transition from one server to a fleet of autoscaling servers.  
* **Detailed Intermediate Steps:**  
  1. **Prepare Machine Image:** Ensure your VM has the Node.js app starting on boot (using pm2 or a systemd service).  
  2. **Create Image:** **Compute Engine \> Images \> Create Image** from the monolith-server disk.  
  3. **Create Instance Template:** **Compute Engine \> Instance Templates \> Create**. Select the custom image you just created.  
  4. **Create Managed Instance Group (MIG):** **Compute Engine \> Instance Groups \> Create**. Choose "Managed", select your template, and set autoscaling (e.g., 1-5 instances based on 60% CPU).  
  5. **Create Load Balancer:** **Network Services \> Load Balancing**. Create an HTTP(S) LB. Set the MIG as the Backend Service.  
* **GCLI Reference:**  
  gcloud compute images create app-v1-image \--source-disk=monolith-server  
  gcloud compute instance-templates create app-template \--image=app-v1-image  
  gcloud compute instance-groups managed create app-mig \--template=app-template \--size=2 \--target-cpu-utilization=0.6

## **Phase 2: Performance & Global Scale**

### **Tutorial 2.1: Caching for Speed (Memorystore)**

* **Goal:** Reduce DB load by caching image metadata.  
* **Intermediate Steps:** 1\. Provision Redis instance. 2\. Install redis npm package. 3\. Implement "Cache-Aside" logic in Express middleware.  
* **Console Workflow:** **Memorystore \> Redis \> Create Instance**. Ensure it's on the same VPC as your MIG.  
* **GCLI Reference:**  
  gcloud redis instances create metadata-cache \--size=1 \--region=us-central1 \--connect-mode=PRIVATE\_SERVICE\_ACCESS

### **Tutorial 2.2: Content Delivery Network (CDN)**

* **Goal:** Serve static images from global edge locations.  
* **Intermediate Steps:**  
  1. **Cloud Storage**: Create a public bucket.  
  2. **App Update**: Change the upload logic to stream to GCS instead of local disk.  
  3. **Load Balancer Update**: Add a **Backend Bucket** to your existing LB.  
  4. **Enable CDN**: Check the "Enable Cloud CDN" box on the backend bucket configuration.  
* **GCLI Reference:**  
  gsutil mb gs://my-app-images  
  gcloud compute backend-buckets create img-backend \--gcs-bucket-name=my-app-images \--enable-cdn

## **Phase 3: Event-Driven Architecture**

### **Tutorial 3.1: Async Workers (Pub/Sub & Functions)**

* **Goal:** Offload heavy resizing tasks.  
* **Intermediate Steps:**  
  1. **Pub/Sub**: Create a topic image-upload.  
  2. **IAM**: Create a Service Account for the function with roles/storage.objectAdmin.  
  3. **Cloud Run Function**: Create a Node.js function triggered by Pub/Sub that uses the sharp library to resize images.  
* **GCLI Reference:**  
  gcloud pubsub topics create image-upload  
  gcloud functions deploy thumbnail-worker \--gen2 \--runtime=nodejs18 \--trigger-topic=image-upload

## **Phase 4: Modern Infrastructure (Containers & K8s)**

### **Tutorial 4.1: Containerization & Cloud Run**

* **Goal:** Serverless containers for the web tier.  
* **Intermediate Steps:** 1\. Create a Dockerfile. 2\. Build via Cloud Build. 3\. Deploy to Cloud Run.  
* **Console Workflow:** **Artifact Registry \> Create Repo**. Then **Cloud Run \> Deploy Container**.  
* **GCLI Reference:**  
  gcloud artifacts repositories create node-app-repo \--repository-format=docker \--location=us-central1  
  gcloud builds submit \--tag us-central1-docker.pkg.dev/PROJECT\_ID/node-app-repo/web-app:v1

### **Tutorial 4.2: Kubernetes Engine (GKE)**

* **Goal:** Full orchestration.  
* **Intermediate Steps:** 1\. Create GKE Cluster. 2\. Define k8s/deployment.yaml and k8s/service.yaml. 3\. Configure Kubernetes Secrets for DB passwords.  
* **GCLI Reference:**  
  gcloud container clusters create scaling-cluster \--num-nodes=3  
  kubectl apply \-f k8s/

### **Tutorial 4.3: Automated CI/CD**

* **Goal:** Push-to-deploy.  
* **Intermediate Steps:** 1\. Connect GitHub to Google Cloud. 2\. Create cloudbuild.yaml with steps for npm test, docker build, and kubectl set image.