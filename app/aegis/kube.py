from kubernetes import config as kube_config


# Inside the cluster Aegis uses its ServiceAccount; from the local machine, ~/.kube/config.
def load_kubernetes_credentials():
    try:
        kube_config.load_incluster_config()
        return "in-cluster"
    except kube_config.ConfigException:
        kube_config.load_kube_config()
        return "kubeconfig"
