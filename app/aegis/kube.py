from kubernetes import config as kube_config


# Uses the ServiceAccount inside the cluster, or ~/.kube/config on the local machine.
def load_kubernetes_credentials():
    try:
        kube_config.load_incluster_config()
        return "in-cluster"
    except kube_config.ConfigException:
        kube_config.load_kube_config()
        return "kubeconfig"
