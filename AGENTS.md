# AGENTS Instructions

- **Backend:** Django
- **Frontend:** Django Templates with vanilla JavaScript
- **Database:** PostgreSQL
- **Testing:** pytest

## Development Practices

- Use `black` for Python code formatting.
- Use `isort` to sort imports.
- Follow PEP 8 guidelines.
- Write tests for all new features and bug fixes.

## Docker Base Image & Metapackage Dependency Rules

- A imagem base Docker (`ctezlifrn/avaintegrationbase:<versao>`) especificada em `ARG BASEIMAGE` no `Dockerfile` é
  publicada no Docker Hub via CI/CD quando uma nova versão/tag do repositório `avaintegration_metapackage` é lançada.
- Ao atualizar a dependência `avaintegration-metapackage` no `pyproject.toml`, **NÃO** altere `ARG BASEIMAGE` no
  `Dockerfile` a menos que a versão correspondente da imagem Docker já tenha sido publicada no Docker Hub. Caso a
  versão do metapackage ainda não possua uma imagem base publicada no Docker Hub, mantenha `ARG BASEIMAGE` na última
  versão disponível para evitar erros de `image not found` no build.

## How to Run Tests

```bash
sas test integrador
```

## How to use Docker Compose

In this project we use `sas` as short to `docker compose`.
