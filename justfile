import './helm.just'

default:
    @just -l


tag VERSION:
    @git tag -s services-api-helm-chart-v{{VERSION}} -m "Release new services-api helm chart v{{VERSION}}"