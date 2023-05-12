#!/usr/bin/env python3

import json
import subprocess
import sys

TARGET_TAG = 'latest'
ECS_CLUSTER = 'rust-ecs-prod'

def main():
    """CLI entrypoint of the program."""
    if len(sys.argv) < 2:
        usage()
    repository_name = sys.argv[1]
    images = get_images(repository_name)
    isRetry = None
    while True:
        selected_image_index = let_user_pick_image(images, isRetry)
        if selected_image_index == -1:
            exit(0)

        if selected_image_index is not None:
            break
        else:
            isRetry = True

    image = images[selected_image_index]
    imageTags = image.get("imageTags",[])
    if TARGET_TAG in imageTags:
        err(f"selected image already tagged as {TARGET_TAG}")

    eprint(f"selected option: {image}\n")
    manifest = get_image_manifest(repository_name, image["imageDigest"])
    retag_image(repository_name,manifest)
    image_pushed_at = format_time(image["imagePushedAt"])
    eprint(f"image pushed at {image_pushed_at} retaged as '{TARGET_TAG}'\n")
    if can_redeploy(repository_name):
        redeployed = force_redeploy()
        print(
            f'{"successfully rollback and re-deploy" if redeployed else "Successfully rolled back the image, but redeploying the service with the same name failed"}'
        )
    else:
        eprint(
            "Successfully rolled back the image, but no service with the same name to redeploy found"
        )

def let_user_pick_image(images, isRetry=None):
    if isRetry is None:
        print("Please choosean image to rollback:\n")
        for idx, image in enumerate(images):
            image_pushed_at = format_time(image["imagePushedAt"])
            tags = ", ".join(image.get("imageTags", []))
            print(f'{idx + 1}) {image_pushed_at} {f"({tags})" if tags != "" else ""}')
        print("")
    else:
        print(f"Invalid value, please check the list of possible values...\n")

    i = input("Enter image number (or 0 to exit): ")
    try:
        idx = int(i)
        if -1 < idx <= len(images):
            return idx-1
    except:
        pass
    return None

def get_images(repository_name):
    """Call ecr to get available images"""
    eprint("obtaining available images")
    try:
        out = json.loads( run_command([
            "aws", "ecr", "describe-images",
            "--repository-name", repository_name,
            "--no-paginate"
        ]).stdout)
    except subprocess.CalledProcessError as e:
        err(f"failed to get availabe images from repository: {e}" )

    return list(sorted(out["imageDetails"], key=lambda image: image["imagePushedAt"], reverse=True))

def get_image_manifest(repository_name, imageDigest):
    """Call ecr batch-get-image to get the image manifest"""
    try:
        out = json.loads(
            run_command(
                [
                    "aws",
                    "ecr",
                    "batch-get-image",
                    "--repository-name",
                    repository_name,
                    "--image-ids",
                    f"imageDigest={imageDigest}",
                ]
            ).stdout
        )
    except subprocess.CalledProcessError as e:
        err(f"failed to get availabe images from repository: {e}" )

    return out["images"][0]["imageManifest"]


def retag_image(repository_name, manifest):
    """ """
    try:
        out = json.loads( run_command([
            "aws", "ecr", "put-image",
            "--repository-name", repository_name,
            "--image-manifest", manifest,
            "--image-tag", TARGET_TAG
        ]).stdout)
    except subprocess.CalledProcessError as e:
        err(f"failed to re-tag image as {TARGET_TAG}")

    return True

def can_redeploy(repository_name):
    """return True IFF there is a service with the same name of the repository."""
    try:
        out = json.loads( run_command([
            "aws", "ecs", "list-services",
            "--cluster", ECS_CLUSTER,
            "--no-paginate"
        ]).stdout)

        services = out["serviceArns"]
        return any(repository_name == service.split('/')[-1] for service in services)
    except subprocess.CalledProcessError as e:
        err(f"failed to list services in cluste {ECS_CLUSTER}")

def force_redeploy(service_name):
    """Force redeploy on ecs"""
    try:
        out = json.loads( run_command([
            "aws", "ecs", "update-service",
            "--cluster", ECS_CLUSTER,
            "--service", service_name,
            "--force-new-deployment"
        ]).stdout)

        return True
    except subprocess.CalledProcessError as e:
        err(f"failed to re-deploy service {service_name}")


###############
#  Utilities  #
###############

def format_time(time):
    return time.replace("T", " ").replace("+", " +")

def usage():
    """ print usage help and exit."""
    print("error: missing argument, you need to pass the repository name to use. e.g:")
    print("aws-rollback.py <repository name>")
    exit(1)

def eprint(*args, **kwargs):
    """Just like print(), but outputs on stderr."""
    print(*args, file=sys.stderr, **kwargs)


def err(*args, **kwargs):
    """Show the error message and exit with status 1."""
    eprint("error:", *args, **kwargs)
    exit(1)


def run_command(*args, **kwargs):
    """Run a CLI program capturing stdout. Raise an exception if it fails."""
    return subprocess.run(
        *args,
        stdout=subprocess.PIPE,
        check=True,
        **kwargs,
    )


####################
#  CLI Invocation  #
####################


if __name__ == "__main__":
    main()
