<img width="960" alt="Capture-9" src="https://github.com/user-attachments/assets/5dfe4c67-1eb6-4534-8c6c-41369d65042a" /># Obtaining API Key and URL for Qdrant Vector Database

To integrate Qdrant's vector database into your applications, you'll need to acquire a unique API key and the corresponding cluster URL. These credentials authenticate and direct your application's requests to your specific Qdrant instance. Follow the steps below to obtain them:

## Step 1: Register for a Qdrant Cloud Account

1. **Access the Qdrant Cloud Portal:**
   - Navigate to the [Qdrant Cloud website](https://cloud.qdrant.io/).

2. **Sign Up:**
   - Click on the "Cloud" button located at the top-right corner.
   - Choose your preferred registration method:
     - **Email:** Enter your email address and create a password.
     - **Google or GitHub:** Authenticate using your existing Google or GitHub account credentials.

3. **Verify Your Account:**
   - Follow the on-screen instructions to verify your email address, if prompted.

## Step 2: Create a New Qdrant Cluster

1. **Initiate Cluster Creation:**
   - After logging in, click on the "Create First Cluster" button or navigate to the "Clusters" section and select "Create Cluster."

2. **Configure Cluster Settings:**
   - Provide a unique name for your cluster.
   - Select your preferred cloud provider (e.g., AWS, GCP, Azure).
   - Choose the desired region for deployment.
   - Specify the resources allocated to your cluster, such as CPU, RAM, and storage.

3. **Deploy the Cluster:**
   - Review your configurations and confirm the creation.
   - The provisioning process may take a few moments. Once complete, your cluster will be listed under the "Clusters" section.

## Step 3: Obtain the Cluster URL

1. **Access Cluster Details:**
   - In the "Clusters" section, locate your newly created cluster.
   - Under the "Actions" column, click on the "Dashboard" button associated with your cluster.

2. **Retrieve the Cluster URL:**
   - Within the cluster dashboard, note the URL displayed. This URL is essential for connecting to your Qdrant instance.

## Step 4: Generate an API Key

1. **Navigate to API Key Management:**
   - Within the cluster dashboard, find the "API Keys" section.

2. **Create a New API Key:**
   - Click on the "Create" button to initiate the API key generation process.
   - Assign a descriptive name to your API key for easy identification.
   - Optionally, set an expiration period (default is 90 days). Leaving this field empty will result in a non-expiring key.
   - Define the key's permissions:
     - **Cluster-Wide Permissions:** Choose between manage/write (default) or read-only access.
     - **Collection-Specific Permissions:** To restrict access to specific collections, select the "Collections" tab and specify the desired collections.

3. **Finalize and Retrieve the API Key:**
   - Click on the "Create" button to generate the API key.
   - **Important:** The API key will be displayed only once. Ensure you copy and securely store it, as it cannot be retrieved again. If lost, a new key must be generated.

## Step 5: Test Your Credentials

To verify that your API key and cluster URL are functioning correctly, execute the following command in your terminal:

```bash
curl -X GET 'https://your-cluster-url:6333' --header 'api-key: your-api-key'
```

A successful response will resemble:

```json
{"title":"qdrant - vector search engine","version":"1.13.0","commit":"ffda0b90c8c44fc43c99adab518b9787fe57bde6"}
```


This confirms that your credentials are valid and your Qdrant instance is accessible.

## Security Best Practices

- **Protect Your API Key:** Treat your API key like a password. Do not expose it in public repositories, logs, or unsecured environments.
- **Regular Rotation:** Periodically regenerate and update your API keys to enhance security.
- **Restrict Permissions:** Assign the minimum necessary permissions to each API key based on its intended use.
- **Enable TLS:** To prevent potential data interception, ensure that TLS is enabled when transmitting your API key over networks.

By following these steps, you'll successfully acquire the necessary credentials to integrate and interact with your Qdrant vector database instance.
